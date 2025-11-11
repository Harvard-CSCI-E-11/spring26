"use strict";
console.log("start");

/* lab5: imageboard.js
 * Code for uploading and displaying images.
 */

const REFRESH_RATE = 5000;
const UPLOAD_TIMEOUT_SECONDS = 20;
const MAX_FILE_UPLOAD = 10 * 1000 * 1000; // 10 MB

function setText(selector, text) {
    const el = document.querySelector(selector);
    if (el) el.textContent = text;
}

/** lab5 show_images() function. */
function show_images() {
    console.log("lab5 show_images");

    fetch("api/get-images", { method: "GET" })
        .then((r) => {
            if (!r.ok) {
                setText("#message-container", `Error: ${r.status} ${r.statusText}`);
                return Promise.reject(new Error(r.statusText));
            }
            return r.json();
        })
        .then((obj) => {
            // Update or create Tabulator table
            const existing = Tabulator.findTable("#message-table")[0];
            if (existing) {
                existing.replaceData(obj);
                return;
            }

            new Tabulator("#message-table", {
                data: obj,
                layout: "fitColumns",
                rowHeight: 120,
                columns: [
                    { title: "#", field: "image_id", width: 20 },
                    { title: "Created", field: "created" },
                    { title: "Message", field: "message" },
                    {
                        title: "Photo",
                        field: "image_id",
                        formatter: (cell) => {
                            const id = cell.getValue();
                            if (!id) return "n/a";
                            const src = `/api/get-image?image_id=${encodeURIComponent(id)}`;
                            return `<img src="${src}" alt="Image" style="width:auto; height:115px;" class="clickable-image">`;
                        },
                    },
                    {
                        title: "Celebrity",
                        field: "celeb",
                        formatter: (cell) => {
                            const celeb = cell.getValue();
                            const c0 = celeb && celeb[0];
                            if (!c0) return "n/a";
                            const href = c0.Urls && c0.Urls[0] ? `https://${c0.Urls[0]}` : "#";
                            return `Name: <a href="${href}">${c0.Name}</a><br>Match Confidence: ${c0.MatchConfidence}`;
                        },
                    },
                ],
                placeholder: "No lab5 messages yet",
            });

            initImagePopups();
        })
        .catch((error) => {
            setText("#table-container", `Uncaught error: ${error.message}`);
            console.error(error);
        });
}

/** Enable/disable submit button based on inputs */
function enable_disable_submit_button() {
    const imageEl = document.querySelector("#image-file");
    const keyEl = document.querySelector("#api-key");
    const secretEl = document.querySelector("#api-secret-key");
    const submitBtn = document.querySelector("#submit-button");
    const statusMsg = document.querySelector("#status-message");

    const hasImage = !!(imageEl && imageEl.files && imageEl.files.length > 0);
    const hasKey = !!(keyEl && keyEl.value.length > 0);
    const hasSecret = !!(secretEl && secretEl.value.length > 0);

    const enable = hasImage && hasKey && hasSecret;

    if (submitBtn) submitBtn.disabled = !enable;
    if (statusMsg) statusMsg.textContent = enable ? "ready to upload!" : "";
}

/** Image popups using vanilla JS (event delegation) */
function initImagePopups() {
    const popup = document.querySelector("#image-popup");
    const popupImg = document.querySelector("#popup-img");
    if (!popup || !popupImg) return;

    document.addEventListener("click", (evt) => {
        const img = evt.target.closest(".clickable-image");
        if (img) {
            popupImg.src = img.getAttribute("src");
            popup.style.display = "block";
        } else if (evt.target.closest("#image-popup")) {
            popup.style.display = "none";
        }
    }, { passive: true });
}

/*
 * Uploads a image using a presigned post. See:
 * https://aws.amazon.com/blogs/compute/uploading-to-amazon-s3-directly-from-a-web-or-mobile-application/
 * https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
 *
 * Presigned post is provided by the /api/post-image call (see below)
 */
function upload_image_post(imageFile) {
    setText("#status-message", "Requesting signed upload...");

    const formData = new FormData();
    formData.append("api_key", (document.querySelector("#api-key") || {}).value || "");
    formData.append("api_secret_key", (document.querySelector("#api-secret-key") || {}).value || "");
    formData.append("message", (document.querySelector("#message") || {}).value || "");
    formData.append("image_data_length", imageFile.size);

    fetch("api/post-image", { method: "POST", body: formData })
        .then((r) => {
            if (!r.ok) {
                setText("#status-message", `Error: ${r.status} ${r.statusText}`);
                return Promise.reject(new Error(r.statusText));
            }
            return r.json();
        })
        .then((obj) => {
            console.log("api/post-image returned obj=", obj);
            if (obj.error) throw new Error(obj.error);

            setText("#status-message", `Uploading image ${obj.image_id}...`);

            const uploadFormData = new FormData();
            for (const [k, v] of Object.entries(obj.presigned_post.fields)) {
                uploadFormData.append(k, v);
            }
            uploadFormData.append("file", imageFile); // order matters

            const ctrl = new AbortController();
            const timeout = setTimeout(() => ctrl.abort(), UPLOAD_TIMEOUT_SECONDS * 1000);

            return fetch(obj.presigned_post.url, {
                method: "POST",
                body: uploadFormData,
                signal: ctrl.signal,
            }).finally(() => clearTimeout(timeout));
        })
        .then((uploadResponse) => {
            if (!uploadResponse.ok) {
                setText("#upload_message", `Error uploading image status=${uploadResponse.status} ${uploadResponse.statusText}`);
                return Promise.reject(new Error(uploadResponse.statusText));
            }
            setText("#status-message", "Image uploaded.");
            const imageEl = document.querySelector("#image-file");
            if (imageEl) imageEl.value = ""; // clear selected file
        })
        .catch((error) => {
            if (error.name === "AbortError") {
                setText("#status-message", `Timeout (${UPLOAD_TIMEOUT_SECONDS}s) uploading image.`);
            } else {
                setText("#status-message", `An error occurred: ${error.message}`);
            }
            console.error(error);
        })
        .finally(() => {
            enable_disable_submit_button();
            show_images();
        });
}

/** Handle upload button */
function upload_image() {
    const imageEl = document.querySelector("#image-file");
    const imageFile = imageEl && imageEl.files && imageEl.files[0];
    if (!imageFile) {
        setText("#status-message", "Please choose an image.");
        return;
    }
    if (imageFile.size > MAX_FILE_UPLOAD) {
        setText("#status-message", `That file is too big to upload. Please choose a file smaller than ${MAX_FILE_UPLOAD} bytes.`);
        return;
    }
    upload_image_post(imageFile);
}

/** DOM ready */
document.addEventListener("DOMContentLoaded", () => {
    console.log("lab5 ready function running.");

    // Insert file input before submit group
    const pos = document.getElementById("submit-group");
    if (pos) {
        pos.insertAdjacentHTML("beforebegin", `
            <div class="pure-control-group">
                <label for="message">IMAGE:</label>
                <input type="file" id="image-file" name="image" class="uploadf"/>
            </div>
        `);
    }

    // Convert submit button into a regular button
    const submitBtn = document.getElementById("submit-button");
    if (submitBtn) {
        submitBtn.setAttribute("type", "button");
        submitBtn.value = "UPLOAD";
        submitBtn.addEventListener("click", upload_image);
    }

    // Hook up change handlers to (re)compute button enabled state
    enable_disable_submit_button();
    document.addEventListener("change", (e) => {
        if (e.target.matches("#image-file, #api-key, #api-secret-key")) {
            enable_disable_submit_button();
        }
    }, { passive: true });

    // Initial table load
    show_images();
});

/* lab5 startup
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
