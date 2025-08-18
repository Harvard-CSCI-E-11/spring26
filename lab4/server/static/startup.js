/* lab4 startup
 * See https://developer.mozilla.org/en-US/docs/Web/API/Window/setInterval
 * for an expaination of this.
 */
const DELAY = 5000;
function loop() {
    show_messages();
    setTimeout(loop, DELAY);
}


$( document ).ready( function() {
    loop();
});
