"use strict";
console.log('start');

/* jshint esversion: 8 */
const UPLOAD_TIMEOUT_SECONDS = 20;
const MAX_FILE_UPLOAD = 10*1000*1000;

////////////////////////////////////////////////////////////////
/// Enable the image-file upload when a file is selected and both the api-key and api-secret-key are provided.
function enable_disable_upload_button()
{
    const enable = $('#image-file').val().length > 0 &&
          $('#api-key').val().length > 0 &&
          $('#api-secret-key').val().length > 0;
    $('#upload-button').prop('disabled', !enable);
    if (enable) {
        $('#message').text('ready to upload!');
    } else {
        $('#message').text(''); // clear the message if button is disabled
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
 * Presigned post is provided by the /api/new-image call (see below)
 */
function upload_image_post(imageFile) {
    // Get a presigned post from the server
    $('#message').text(`Requesting signed upload...`);
    let formData = new FormData();
    formData.append("api_key", $('#api-key').val());
    formData.append("api_secret_key", $('#api-secret-key').val());
    formData.append("image_data_length", imageFile.size);

    fetch('api/new-image', { method: "POST", body: formData })
        .then(r => {
            if (!r.ok) {
                $('#message').text(`Error: ${r.status} ${r.statusText}`);
                throw new Error(`Failed to get signed upload URL: ${r.statusText}`);
            }
            return r.json();    // returned to next .then()
        })
        .then(obj => {
            console.log("api/new-image returned obj=",obj);
            $('#message').text(`Uploading image ${obj.image_id}...`);
            const uploadFormData = new FormData();
            for (const field in obj.presigned_post.fields) {
                uploadFormData.append(field, obj.presigned_post.fields[field]);
            }
            uploadFormData.append("file", imageFile); // order matters!

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
            $('#message').text('Image uploaded.');
            $('#image-file').val(''); // clear the uploaded image
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                $('#message').text(`Timeout (${UPLOAD_TIMEOUT_SECONDS}s) uploading image.`);
            } else {
                $('#message').text(`An error occurred: ${error.message}`);
            }
        });
    // A successful POST clears the image to upload.
    // Clear the button and list the images
    enable_disable_upload_button();
    list_images();
}

/** Run the server's list-images
 * This version shows all uploaded movies and requires no authentication.
 */
function list_images() {
    fetch('api/list-images', { method: "GET" })
        .then(r => {
            if (!r.ok) {
                $('#image-container').text(`Error: ${r.status} ${r.statusText}`);
                throw new Error(`Failed to get images: ${r.statusText}`);
            }
            return r.json();
        })
        .then(obj => {
            // Clear the table container and initialize Tabulator
            $('#table-container').html('<div id="image-table"></div>');

            // Create a new Tabulator table
            new Tabulator("#image-table", {
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
                            return `<img src="${url}" alt="Image" style="width:auto; height:115px;" class="clickable-image">`;
                        }
                    },
                    { title: "Celebrity", field: "celeb_html", formatter:"html"}
                ],
                placeholder: "No data available", // Displayed when there is no data
            });
            initImagePopups();
        })
        .catch(error => {
            $('#table-container').text(`Uncaught error: ${error.message}`);
        });
}



/** The function that is called when the upload_image button is clicked.
 * It validates the image to be uploaded and then calls the upload function.
 */
function upload_image()
{
    const imageFile   = $('#image-file').prop('files')[0];
    if (imageFile.fileSize > MAX_FILE_UPLOAD) {
        $('#message').text(`That file is too big to upload. Please chose a file smaller than ${MAX_FILE_UPLOAD} bytes.`);
        return;
    }
    upload_image_post(imageFile);
}

$( document ).ready( function() {
    console.log("lab4.js ready function running.")
    // set the correct enable/disable status of the upload button, and configure
    // it to change when any of the form controls change
    enable_disable_upload_button();
    $('.uploadf').on('change', enable_disable_upload_button );
    $('#upload-button').on('click', upload_image);
});


console.log('lab4.js');
