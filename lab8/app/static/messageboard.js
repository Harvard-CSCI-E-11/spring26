/** lab4 show_messages() function.
 * This version shows all uploaded movies and requires no authentication.
 */
function show_messages() {
    console.log("lab4 show_messages");
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
	    let table = Tabulator.findTable("#message-table")[0];
	    if (table) {
		// Table exists: Update the data
		table.replaceData(obj);
	    } else {
		// Table doesn't exist: Create it
		table = new Tabulator("#message-table", {
		    data: obj,
		    layout: "fitColumns",
		    columns: [
			{ title: "Posted", field: "created" },
			{ title: "Message", field: "message" },
		    ],
		    placeholder: "No lab4 messages yet",
		});
	    }
        })
        .catch(error => {
            $('#message-container').text(`Uncaught error: ${error.message}`);
        });
}
