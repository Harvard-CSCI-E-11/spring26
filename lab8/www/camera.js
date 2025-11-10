// Ensure this script is hosted on an HTTPS server
const UPLOAD_INTERVAL_SECONDS = 5;
const UPLOAD_TIMEOUT_SECONDS = 60;
var  frames_uploaded = 0;

console.log("TODO - compute the correct URL")

function post_image(image) {
    console.log("post_image",image);
    let formData = new FormData();
    formData.append("api_key", $('#api-key').val());
    formData.append("api_secret_key", $('#api-secret-key').val());
    fetch('api/post-image', { method: "POST", body: formData })
        .then(r => {
            if (!r.ok) {
                $('#status-message').text(`Error: ${r.status} ${r.statusText}`);
                throw new Error(`Failed to get signed upload URL: ${r.statusText}`);
            }
            return r.json();    // returned to next .then()
        })
        .then(obj => {
	    if (obj.error) {
                throw { message: obj.error };
	    }
            frames_uploaded += 1;
            $('#status-message').text(`Uploading frame ${frames_uploaded} as image ${obj.image_id}.`);

            // Now use the presigned_post to upload to s3
            const uploadFormData = new FormData();
            for (const field in obj.presigned_post.fields) {
                uploadFormData.append(field, obj.presigned_post.fields[field]);
            }
            uploadFormData.append("file", image); // order matters!

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
                $('#upload_message').text(
                    `Error uploading image status=${uploadResponse.status} ${uploadResponse.statusText}`);
                throw new Error(`Upload failed: ${uploadResponse.statusText}`);
            }
            $('#status-message').text('Image ${frames_uploaded} uploaded.');
            $('#image-file').val(''); // clear the uploaded image
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                $('#status-message').text(`Timeout (${UPLOAD_TIMEOUT_SECONDS}s) uploading image.`);
            } else {
                $('#status-message').text(`An error occurred: ${error.message}`);
            }
        });
}


async function run_camera() {
    // Check if the browser supports media devices
    console.log("run_camera...");
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Your browser does not support camera access.");
        return;
    }

    try {
        // Access the camera
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });

        // Create a video element to display the stream
        const video = document.createElement("video");
        document.body.appendChild(video);
        video.srcObject = stream;
        console.log("start video.play");
        await video.play();
        console.log("continue video.play...");

        // Create a canvas to capture images
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");

        // Function to capture and send an image
        const captureAndSend = async () => {
            // Set canvas size to match video size
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            // Draw the current video frame to the canvas
            context.drawImage(video, 0, 0, canvas.width, canvas.height);

            // Convert the canvas to a data URL
            canvas.toBlob(post_image, "image/jpeg", 0.95);
        };

        // Capture and send an image every UPLOAD_INTERVAL_SECONDS seconds
        setInterval(captureAndSend, UPLOAD_INTERVAL_SECONDS * 1000);
    } catch (error) {
        console.error("Error accessing camera:", error);
    }
};

$( document ).ready( function() {
    console.log("lab7 ready function running.");
    $('#run-button').on('click', run_camera);
});
