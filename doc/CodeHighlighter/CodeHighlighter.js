/**
 * Global constant for the ID of the JSON configuration file on Google Drive.
 * REPLACE 'YOUR_JSON_FILE_ID_HERE' with the actual ID of your config file.
 */
const CONFIG_FILE_ID = 'YOUR_JSON_FILE_ID_HERE';

/**
 * Runs automatically when the document is opened. Creates a custom menu.
 */
function onOpen() {
  const ui = DocumentApp.getUi();
  ui.createMenu('📝 Code Highlighter')
      .addItem('✅ Apply Formatting', 'applyConditionalHighlighting')
      .addSeparator()
      .addItem('❌ Remove All Custom Formatting (Undo)', 'removeAllHighlights')
      .addToUi();
}

/**
 * Reads the JSON configuration file from Google Drive.
 * @returns {Array<Object>} An array of formatting objects.
 */
function getConfig() {
  try {
    const file = DriveApp.getFileById(CONFIG_FILE_ID);
    const content = file.getBlob().getDataAsString();
    return JSON.parse(content);
  } catch (e) {
    DocumentApp.getUi().alert('Configuration Error',
      'Could not read the JSON file from Google Drive. Check the file ID and permissions.',
      DocumentApp.getUi().ButtonSet.OK);
    Logger.log(`Configuration Error: ${e.toString()}`);
    return [];
  }
}

/**
 * Main function to apply conditional highlighting based on the regex configuration.
 */
function applyConditionalHighlighting() {
  const config = getConfig();
  if (config.length === 0) return;

  const doc = DocumentApp.getActiveDocument();
  const body = doc.getBody();
  const ui = DocumentApp.getUi();

  // Show a status dialog
  ui.showSidebar(HtmlService.createHtmlOutput('<p>Applying formatting... Please wait.</p>').setTitle('Status'));

  // 1. Process Main Body
  processElement(body, config);

  // 2. Process Tables
  for (let i = 0; i < body.getNumChildren(); i++) {
    const child = body.getChild(i);
    if (child.getType() === DocumentApp.ElementType.TABLE) {
      processTable(child.asTable(), config);
    }
  }

  // 3. Process Footnotes
  doc.getFootnotes().forEach(footnote => {
    const section = footnote.getFootnoteContents();
    processElement(section, config);
  });

  // Close the status dialog and confirm completion
  ui.showSidebar(HtmlService.createHtmlOutput('<p>Formatting complete!</p>').setTitle('Status'));
  Utilities.sleep(2000);
  ui.showSidebar(HtmlService.createHtmlOutput('').setTitle(''));

  // The custom menu ensures all changes are automatically saved.
}

/**
 * Traverses a table element (including all cells and paragraphs within)
 * @param {GoogleAppsScript.Document.Table} table The table element to process.
 * @param {Array<Object>} config The array of formatting objects.
 */
function processTable(table, config) {
  for (let i = 0; i < table.getNumRows(); i++) {
    const row = table.getRow(i);
    for (let j = 0; j < row.getNumCells(); j++) {
      const cell = row.getCell(j);
      processElement(cell, config);
    }
  }
}

/**
 * Core processing function: iterates through elements and applies regex and formatting.
 * @param {GoogleAppsScript.Document.ContainerElement} container The element (Body, TableCell, or FootnoteSection) to process.
 * @param {Array<Object>} config The array of formatting objects.
 */
function processElement(container, config) {
  for (let i = 0; i < container.getNumChildren(); i++) {
    const child = container.getChild(i);

    if (child.getType() === DocumentApp.ElementType.PARAGRAPH ||
        child.getType() === DocumentApp.ElementType.LIST_ITEM) {

      const paragraph = child.asText() ? child : child.asParagraph();
      const text = paragraph.getText();

      // Iterate through the config sequentially (last applied formatting will dominate)
      config.forEach(item => {
        try {
          const re = new RegExp(item.regex, 'g');
          let match;

          while ((match = re.exec(text)) !== null) {
            const start = match.index;
            const end = start + match[0].length;

            // Apply all specified formatting properties
            if (item.backgroundColor !== undefined) {
              paragraph.setBackgroundColor(start, end - 1, item.backgroundColor);
            }
            if (item.foregroundColor !== undefined) {
              paragraph.setForegroundColor(start, end - 1, item.foregroundColor);
            }
            if (item.underline !== undefined) {
              paragraph.setUnderline(start, end - 1, item.underline);
            }
          }
        } catch (e) {
          Logger.log(`Regex Error for pattern "${item.regex}": ${e.toString()}`);
        }
      });
    }
    // Recursively handle nested elements
    if (child.isContainerElement && child.getType() !== DocumentApp.ElementType.TABLE) {
        processElement(child.asContainerElement(), config);
    }
  }
}

/**
 * The 'Undo' function. Removes all custom formatting (background, foreground color, underline)
 * that the script would typically set, by resetting them to their default (null) state.
 */
function removeAllHighlights() {
  const doc = DocumentApp.getActiveDocument();
  const ui = DocumentApp.getUi();

  // Custom status dialog
  ui.showSidebar(HtmlService.createHtmlOutput('<p>Removing all custom formatting... Please wait.</p>').setTitle('Status'));

  // Define a function to clear highlights from any text container
  const clearFormatting = (container) => {
    for (let i = 0; i < container.getNumChildren(); i++) {
      const child = container.getChild(i);

      if (child.getType() === DocumentApp.ElementType.PARAGRAPH ||
          child.getType() === DocumentApp.ElementType.LIST_ITEM) {

        try {
          const textElement = child.asText() || child.asParagraph().editAsText();
          const len = textElement.getText().length;

          if (len > 0) {
            // Reset all properties to null (default) state
            textElement.setBackgroundColor(0, len - 1, null);
            textElement.setForegroundColor(0, len - 1, null);
            textElement.setUnderline(0, len - 1, null);
          }
        } catch (e) {
          Logger.log(`Error clearing formatting in child ${i}: ${e.toString()}`);
        }
      }
      // Handle tables recursively
      if (child.getType() === DocumentApp.ElementType.TABLE) {
        const table = child.asTable();
        for (let r = 0; r < table.getNumRows(); r++) {
          for (let c = 0; c < table.getRow(r).getNumCells(); c++) {
            clearFormatting(table.getRow(r).getCell(c));
          }
        }
      }
    }
  };

  // 1. Process Main Body
  clearFormatting(doc.getBody());

  // 2. Process Footnotes
  doc.getFootnotes().forEach(footnote => {
    clearFormatting(footnote.getFootnoteContents());
  });

  // Close the status dialog and confirm completion
  ui.showSidebar(HtmlService.createHtmlOutput('<p>All custom formatting removed!</p>').setTitle('Status'));
  Utilities.sleep(2000);
  ui.showSidebar(HtmlService.createHtmlOutput('').setTitle(''));
}
