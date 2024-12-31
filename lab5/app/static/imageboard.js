"use strict";
console.log('start');

/* lab5: imageboard.js
 * Code for uploading and displaying images.
 */

/* jshint esversion: 8 */
const UPLOAD_TIMEOUT_SECONDS = 20;
const MAX_FILE_UPLOAD = 10*1000*1000;

/** lab5 show_images() function.
 */
function show_images() {
    console.log("lab5 images_messages");
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
                    data: obj, // Assign fetched data to the table
                    layout: "fitColumns", // Fit columns to width of the table
                    rowHeight: 120,
                    columns: [
                        { title: "#", field: "image_id", width:20 },
                        { title: "Created", field: "created" },
                        { title: "S3 Key", field: "s3key" },
                        {
                            title: "Photo",
                            field: "url",
                            formatter: function (cell, formatterParams) {
                                const url = cell.getValue();
                                if (!url) {
                                    return `n/a`;
                                }
                                return `<img src="${url}" alt="Image" style="width:auto; height:115px;" class="clickable-image">`;
                            }
                        },
                        { title: "Celebrity", field: "celeb_html", formatter:"html"}
                    ],
                    placeholder: "No lab5 messages yet", // Displayed when there is no data
                });
                initImagePopups();
            }
        })
        .catch(error => {
            $('#table-container').text(`Uncaught error: ${error.message}`);
        });
}




////////////////////////////////////////////////////////////////
/// Enable the image-file upload when a file is selected and both the api-key and api-secret-key are provided.
function enable_disable_submit_button()
{
    const enable = $('#image-file').val().length > 0 &&
          $('#api-key').val().length > 0 &&
          $('#api-secret-key').val().length > 0;
    $('#submit-button').prop('disabled', !enable);
    if (enable) {
        $('#status-message').text('ready to upload!');
    } else {
        $('#status-message').text(''); // clear the message if button is disabled
    }
}

// This implements the image pop-ups
function initImagePopups()
{
    $(document).on('click', '.clickable-image', function () {
        const imgUrl = $(this).attr('src');  // Get the image URL
        $('#popup-img').attr('src', imgUrl); // Set the image source in the pop-up
        $('#image-popup').fadeIn();          // Show the pop-up
    });

    // When the pop-up is clicked, hide it
    $('#image-popup').on('click', function () {
        $(this).fadeOut();
    });
}

/*
 *
 * Uploads a image using a presigned post. See:
 * https://aws.amazon.com/blogs/compute/uploading-to-amazon-s3-directly-from-a-web-or-mobile-application/
 * https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
 *
 * Presigned post is provided by the /api/post-image call (see below)
 */
function upload_image_post(imageFile) {
    // Get a presigned post from the server
    $('#status-message').text(`Requesting signed upload...`);
    let formData = new FormData();
    formData.append("api_key", $('#api-key').val());
    formData.append("api_secret_key", $('#api-secret-key').val());
    formData.append("image_data_length", imageFile.size);

    fetch('api/post-image', { method: "POST", body: formData })
        .then(r => {
            if (!r.ok) {
                $('#status-message').text(`Error: ${r.status} ${r.statusText}`);
                throw new Error(`Failed to get signed upload URL: ${r.statusText}`);
            }
            return r.json();    // returned to next .then()
        })
        .then(obj => {
            console.log("api/post-image returned obj=",obj);
	    if (obj.error) {
                throw { message: obj.error };
	    }
            $('#status-message').text(`Uploading image ${obj.image_id}...`);

            // Now use the presigned_post to upload to s3
            const uploadFormData = new FormData();
            for (const field in obj.presigned_post.fields) {
                uploadFormData.append(field, obj.presigned_post.fields[field]);
            }
            uploadFormData.append("file", imageFile); // order matters!

            // Use an AbortController for the timeout:
            // https://developer.mozilla.org/en-US/docs/Web/API/AbortController
            const ctrl = new AbortController();
            setTimeout(() => ctrl.abort(), UPLOAD_TIMEOUT_SECONDS * 1000);
            return fetch(obj.presigned_post.url, {
                method: "POST",
                body: uploadFormData,
                signal: ctrl.signal
            });
        })
        .then(uploadResponse => {
            if (!uploadResponse.ok) {
                $('#upload_message').text(`Error uploading image status=${uploadResponse.status} ${uploadResponse.statusText}`);
                throw new Error(`Upload failed: ${uploadResponse.statusText}`);
            }
            $('#status-message').text('Image uploaded.');
            $('#image-file').val(''); // clear the uploaded image
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                $('#status-message').text(`Timeout (${UPLOAD_TIMEOUT_SECONDS}s) uploading image.`);
            } else {
                $('#status-message').text(`An error occurred: ${error.message}`);
            }
        });
    // A successful POST clears the image to upload.
    // Clear the button and list the images
    enable_disable_submit_button();
    show_images();
}

/** The function that is called when the upload_image button is clicked.
 * It validates the image to be uploaded and then calls the upload function.
 */
function upload_image()
{
    const imageFile   = $('#image-file').prop('files')[0];
    if (imageFile.fileSize > MAX_FILE_UPLOAD) {
        $('#status-message').text(`That file is too big to upload. Please chose a file smaller than ${MAX_FILE_UPLOAD} bytes.`);
        return;
    }
    upload_image_post(imageFile);
}

$( document ).ready( function() {
    console.log("lab5 ready function running.")

    // add the field to the form
    const pos = document.getElementById('submit-group');
    pos.insertAdjacentHTML('beforebegin',`
      <div class='pure-control-group'>
        <label for='message'>IMAGE:</label>
        <input type='file' id='image-file' name='image' class='uploadf'/>
      </div>`);
    // change the submit-button from a SUBMIT into a BUTTON
    document.getElementById('submit-button').setAttribute('type','button');
    document.getElementById('submit-button').value='UPLOAD';

    // set the correct enable/disable status of the upload button, and configure
    // it to change when any of the form controls change
    enable_disable_submit_button();
    $('.uploadf').on('change', enable_disable_submit_button );
    $('#submit-button').on('click', upload_image);
});
