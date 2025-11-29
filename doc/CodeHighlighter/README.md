# 📝 Google Docs Code Highlighter

This project contains a Google Apps Script designed to apply syntax-like formatting (background color, font color, and underlining) to strings in a Google Doc that match specific regular expressions. The script uses a table-driven approach, reading configuration from a JSON file stored on Google Drive.

## ⚙️ Installation and Setup

**The script must be installed individually by every user (you and your co-teacher) who wishes to run it in a specific Google Doc.**

### Step 1: Upload the Configuration File

1.  **Upload** the `highlighter_config.json` file to your Google Drive.
2.  Right-click the uploaded file, select **"Get link,"** and ensure the sharing setting is set to **"Anyone with the link"** or explicitly shared with your co-teacher.
3.  **Copy the File ID** from the URL. The ID is the long string in the middle:
    `https://drive.google.com/file/d/THIS_IS_THE_ID/view`

### Step 2: Install the Apps Script

1.  **Open** the Google Doc where you want to use the highlighter.
2.  Go to **Extensions > Apps Script** to open the Script Editor in a new tab.
3.  If there is existing boilerplate code (`function myFunction()`), delete it.
4.  **Copy and Paste** the entire content of `CodeHighlighter.js` into the Script Editor.
5.  **Crucially:** Find the line in the script editor and **replace the placeholder** with the File ID you copied in Step 1.

    ```javascript
    const CONFIG_FILE_ID = 'YOUR_JSON_FILE_ID_HERE'; // <-- REPLACE THIS
    ```

6.  Click the **Save** icon (floppy disk) and name the script (e.g., `Code Highlighter`).

### Step 3: Run the Script (First Time)

1.  Switch back to your Google Doc. You may need to refresh the page.
2.  The **"📝 Code Highlighter"** menu should now appear next to the "Extensions" menu.
3.  Click **📝 Code Highlighter > ✅ Apply Formatting**.
4.  **Authorization:** On the first run, Google will prompt you to authorize the script. Follow the prompts:
    * Click **"Review permissions"**.
    * Select your Google Account.
    * Click **"Advanced"**, then click **"Go to Code Highlighter (unsafe)"** (this is normal for self-written scripts).
    * Click **"Allow"**.
5.  After authorization, run the script again: **📝 Code Highlighter > ✅ Apply Formatting**.

---

## 🚀 Usage

Once the script is installed and authorized:

1.  **Apply Formatting:** Click **📝 Code Highlighter > ✅ Apply Formatting**. The script processes the Document Body, Tables, and Footnotes sequentially.
2.  **Undo Highlighting:** Click **📝 Code Highlighter > ❌ Remove All Custom Formatting (Undo)**. This function performs a full reset by removing all custom background color, font color, and underlining set by the script (or manually) in the entire document.

---

## 🎨 Configuration (`highlighter_config.json`)

The script reads an array of objects from your Google Drive JSON file. Each object must contain `regex` and can optionally contain formatting keys. **If a formatting key is omitted, that property will not be changed.**

| Key | Description | Example Value |
| :--- | :--- | :--- |
| `regex` | The regular expression to search for. **(Use JavaScript format - escape backslashes)** | `"\\b(if|else|switch)\\b"` |
| `backgroundColor` | The highlight color. Accepts standard **CSS color names** or **Hex codes**. Use `null` for no highlight. | `"Yellow"` or `"#B7410E"` |
| `foregroundColor` | The **font color**. Accepts standard **CSS color names** or **Hex codes**. | `"Black"` or `"White"` |
| `underline` | A boolean value to turn underlining on or off. | `true` or `false` |
| `description` | *(Optional)* A helpful note for maintenance. | `"Conditional Logic Keywords"` |

**Note on Overlap:** Formatting is applied sequentially in the order it appears in the JSON file. If multiple regex patterns match the same text range, the **formatting properties from the last matching pattern will dominate** that specific text range.
