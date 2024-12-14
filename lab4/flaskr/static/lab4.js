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
    console.log('v1=',$('#api-key').val());
    console.log('enable=',enable);
    $('#upload-button').prop('disabled', !enable);
    if (enable) {
        $('#message').html('ready to upload!');
    } else {
        $('#message').html(''); // clear the message if button is disabled
    }
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
    $('#message').html(`Requesting signed upload...`);
    let formData = new FormData();
    formData.append("api_key", $('#api-key').val());
    formData.append("api_secret_key", $('#api-secret-key').val());
    formData.append("image_data_length", imageFile.size);

    fetch(`api/new-image`, { method: "POST", body: formData })
        .then(r => {
            if (!r.ok) {
                $('#message').html(`Error: ${r.status} ${r.statusText}`);
                throw new Error(`Failed to get signed upload URL: ${r.statusText}`);
            }
            console.log("r=",r);
            return r.json();    // returned to next .then()
        })
        .then(obj => {
            if (obj.error) {
                $('#message').html(`Error getting upload URL: ${obj.message}`);
                throw new Error(`Server error: ${obj.message}`);
            }

            console.log("obj=",obj);
            $('#message').html(`Uploading image ${obj.image_id}...`);
            const uploadFormData = new FormData();
            for (const field in obj.fields) {
                uploadFormData.append(field, obj.fields[field]);
            }
            uploadFormData.append("file", imageFile); // order matters!

            const ctrl = new AbortController();
            setTimeout(() => ctrl.abort(), UPLOAD_TIMEOUT_SECONDS * 1000);
            return fetch(obj.url, {
                method: "POST",
                body: uploadFormData,
                signal: ctrl.signal
            });
        })
        .then(uploadResponse => {
            if (!uploadResponse.ok) {
                $('#upload_message').html(`Error uploading image status=${uploadResponse.status} ${uploadResponse.statusText}`);
                throw new Error(`Upload failed: ${uploadResponse.statusText}`);
            }
            $('#message').html('Image uploaded.');
            $('#image-file').val(''); // clear the uploaded image
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                $('#message').html(`Timeout (${UPLOAD_TIMEOUT_SECONDS}s) uploading image.`);
            } else {
                $('#message').html(`An error occurred: ${error.message}`);
            }
        });
}

/** Run the server's list-upload-movies.
 * This version shows all uploaded movies and requires no authentication.
 */
function list_movies()
{

}


/** The function that is called when the upload_image button is clicked.
 * It validates the image to be uploaded and then calls the upload function.
 */
function upload_image()
{
    const imageFile   = $('#image-file').prop('files')[0];
    console.log('imageFile=',imageFile);

    if (imageFile.fileSize > MAX_FILE_UPLOAD) {
        $('#message').html(`That file is too big to upload. Please chose a file smaller than ${MAX_FILE_UPLOAD} bytes.`);
        return;
    }
    upload_image_post(imageFile);
}

$( document ).ready( function() {
    console.log("index.html ready function running.")
    // set the correct enable/disable status of the upload button, and configure
    // it to change when any of the form controls change
    enable_disable_upload_button();
    $('.uploadf').on('change', enable_disable_upload_button );
    $('#upload-button').on('click', upload_image);
});

console.log('lab4.js');
