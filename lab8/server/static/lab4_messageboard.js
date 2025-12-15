/** lab4 show_messages() function.
 * This version shows all uploaded movies and requires no authentication.
 */
const REFRESH_RATE = 5000;
function show_messages() {
    console.log("lab4 show_messages");
    const container = document.querySelector("#message-container");
    if (!container) {
        throw new Error("no #message-container");
    }

    fetch("api/get-messages", { method: "GET" })
        .then((r) => {
            if (!r.ok) {
                container.textContent = `Error: ${r.status} ${r.statusText}`;
                return Promise.reject(new Error(r.statusText));
            }
            return r.json();
        })
        .then((obj) => {
            // Clear or update the Tabulator table
            const table = Tabulator.findTable("#message-table")[0];
            if (table) {
                // Table exists: update its data
                table.replaceData(obj);
            } else {
                // Table doesn't exist: create it
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
        .catch((error) => {
            container.textContent = `Uncaught error: ${error.message}`;
            console.error(error);
        });
}

/* lab4 startup
 * See https://developer.mozilla.org/en-US/docs/Web/API/Window/setTimeout
 * We use setTimeout() rather than setInterval() so we don't need to deal with overlapping calls.
 */
function loop() {
    show_messages();
    setTimeout(loop, REFRESH_RATE);
}

document.addEventListener("DOMContentLoaded", () => {
    loop();
});
