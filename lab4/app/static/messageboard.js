/** lab4 show_messages() function.
 * This version shows all uploaded movies and requires no authentication.
 */
function show_messages() {
    fetch('api/get-messages', { method: "GET" })
        .then(r => {
            if (!r.ok) {
                $('#message-container').text(`Error: ${r.status} ${r.statusText}`);
                throw new Error(`Failed to get messages: ${r.statusText}`);
            }
            return r.json();
        })
        .then(obj => {
            // Clear the table container and initialize Tabulator
            $('#message-container').html('<div id="message-table"></div>');

            // Create a new Tabulator table
            new Tabulator("#message-table", {
                data: obj, // Assign fetched data to the table
                layout: "fitColumns", // Fit columns to width of the table
                columns: [
                    { title: "Posted", field: "created" },
                    { title: "Message", field: "message" },
                ],
                placeholder: "No messages available yet", // Displayed when there is no data
            });
            SetTimeout(show_messages, 5000); // call again in 5 seconds
        })
        .catch(error => {
            $('#message-container').text(`Uncaught error: ${error.message}`);
        });
}
