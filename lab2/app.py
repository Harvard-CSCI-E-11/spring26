from flask import Flask, request, render_template_string
import logging

app = Flask(__name__)
app.logger.setLevel(logging.INFO)  # Set the logging level directly

# HTML template with form for inputs A and B
html_template = '''
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Simple Addition</title>
  </head>
  <body>
    <h2>Addition of A and B</h2>
    <form method="POST">
      <label for="a">Field A:</label>
      <input type="number" id="a" name="a" required><br><br>
      <label for="b">Field B:</label>
      <input type="number" id="b" name="b" required><br><br>
      <input type="submit" value="Submit">
    </form>
    {% if result is not none %}
      <p>Answer: {{ result }}</p>
    {% endif %}
  </body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():

    # Get client IP address
    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        client_ip = request.remote_addr

    # Get Referrer
    referrer = request.headers.get("Referer", "No Referrer")

    # Get User-Agent
    user_agent = request.headers.get("User-Agent", "No User-Agent")

    result = None
    if request.method == 'POST':
        try:
            # Retrieve input values, convert to integers, and calculate the sum
            a = int(request.form.get('a', 0))
            b = int(request.form.get('b', 0))
            app.logger.info(f"ValidInput. client_ip={client_ip} referrer={referrer} user_agent={user_agent} form={request.form.to_dict()}")
            result = a + b
        except ValueError:
            app.logger.info(f"ValueError. client_ip={client_ip} referrer={referrer} user_agent={user_agent} form={request.form.to_dict()}")
            result = "Invalid input"
    else:
        app.logger.info(f"client_ip={client_ip} referrer={referrer} user_agent={user_agent} request.method={request.method}")

    # Render the HTML template with the result
    return render_template_string(html_template, result=result)

if __name__ == '__main__':
    app.run(debug=True)
