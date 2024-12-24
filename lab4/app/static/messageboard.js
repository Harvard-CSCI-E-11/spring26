/** Run the server's get-chat
 * This version shows all uploaded movies and requires no authentication.
 */
function show_messages() {
    fetch('api/get-messages', { method: "GET" })
        .then(r => {
            if (!r.ok) {
                $('#image-container').text(`Error: ${r.status} ${r.statusText}`);
                throw new Error(`Failed to get messages: ${r.statusText}`);
            }
            return r.json();
        })
        .then(obj => {
            // Clear the table container and initialize Tabulator
            $('#table-container').html('<div id="image-table"></div>');

            // Create a new Tabulator table
            new Tabulator("#message-table", {
                data: obj, // Assign fetched data to the table
                layout: "fitColumns", // Fit columns to width of the table
                rowHeight: 120,
                columns: [
                    { title: "Created", field: "created" },
                    { title: "message", field: "message" },
                ],
                placeholder: "No data available", // Displayed when there is no data
            });
            initImagePopups();
        })
        .catch(error => {
            $('#table-container').text(`Uncaught error: ${error.message}`);
        });
}
