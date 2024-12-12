"use strict";
/* jshint esversion: 8 */
const UPLOAD_TIMEOUT_SECONDS = 20;

////////////////////////////////////////////////////////////////
/// page: /upload
/// Enable the movie-file upload when we have at least 3 characters of title and description
/// We also allow uploading other places
function check_upload_metadata()
{
    const title = $('#movie-title').val();
    const description = $('#movie-description').val();
    const movie_file = $('#movie-file').val();
    $('#upload-button').prop('disabled', (title.length < 3 || description.length < 3 || movie_file.length<1));
}

// This is an async function, which uses async functions.
// You get the results with
//        var sha256 = await computeSHA256(file);
async function computeSHA256(file) {
    // Read the file as an ArrayBuffer
    const arrayBuffer = await file.arrayBuffer();

    // Compute the SHA-256 hash
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);

    // Convert the hash to a hexadecimal string
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
}

/*
 *
 * Uploads a movie using a presigned post. See:
 * https://aws.amazon.com/blogs/compute/uploading-to-amazon-s3-directly-from-a-web-or-mobile-application/
 * https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
 *
 * Presigned post is provided by the /api/new-movie call (see below)
 */
async function upload_movie_post(movie_title, description, movieFile)
{
    // Get a new movie_id
    const movie_data_sha256 = await computeSHA256(movieFile);
    let formData = new FormData();
    formData.append("api_key",     api_key);   // on the upload form
    formData.append("title",       movie_title);
    formData.append("description", description);
    formData.append("movie_data_sha256",  movie_data_sha256);
    formData.append("movie_data_length",  movieFile.fileSize);
    const r = await fetch(`${API_BASE}api/new-movie`, { method:"POST", body:formData});
    const obj = await r.json();
    console.log('new-movie obj=',obj);
    if (obj.error){
        $('#message').html(`Error getting upload URL: ${obj.message}`);
        return;
    }
    const movie_id = window.movie_id = obj.movie_id;

    // The new movie_id came with the presigned post to upload the form data.
    try {
        const pp = obj.presigned_post;
        const formData = new FormData();
        for (const field in pp.fields) {
            formData.append(field, pp.fields[field]);
        }
        formData.append("file", movieFile); // order matters!

        const ctrl = new AbortController();    // timeout
        setTimeout(() => ctrl.abort(), UPLOAD_TIMEOUT_SECONDS*1000);
        const r = await fetch(pp.url, {
            method: "POST",
            body: formData,
        });
        if (!r.ok) {
            $('#upload_message').html(`Error uploading movie status=${r.status} ${r.statusText}`);
            return;
        }
    } catch(e) {
        $('#upload_message').html(`Timeout uploading movie -- timeout is currently ${UPLOAD_TIMEOUT_SECONDS} seconds`);
        return;
    }
    // Movie was uploaded! Clear the form and show the first frame

    $('#upload_message').text('Movie uploaded.'); // .text() for <div>s.
    $('#movie-title').val('');                    // .val() for fields
    $('#movie-description').val('');
    $('#movie-file').val('');

    const track_movie = `/analyze?movie_id=${movie_id}`;
    $('#uploaded_movie_title').text(movie_title);        // display the movie title
    $('#movie_id').text(movie_id);                       // display the movie_id
    $('#image-preview').attr('src',first_frame_url(movie_id));          // display the first frame
    $('#track_movie_link').attr('href',track_movie);

    // Clear the movie uploaded
    $('#upload-preview').show();
    $('#upload-form').hide();
    check_upload_metadata(); // disable the button
}

/* Finally the function that is called when the upload_movie button is clicked */
function upload_movie()
{
    const movie_title = $('#movie-title').val();
    const description = $('#movie-description').val();
    const movieFile   = $('#movie-file').prop('files')[0];

    if (movie_title.length < 3) {
        $('#message').html('<b>Movie title must be at least 3 characters long');
        return;
    }

    if (description.length < 3) {
        $('#message').html('<b>Movie description must be at least 3 characters long');
        return;
    }

    if (movieFile.fileSize > MAX_FILE_UPLOAD) {
        $('#message').html(`That file is too big to upload. Please chose a file smaller than ${MAX_FILE_UPLOAD} bytes.`);
        return;
    }
    $('#upload_message').html(`Uploading movie ...`);

    upload_movie_post(movie_title, description, movieFile);
}
