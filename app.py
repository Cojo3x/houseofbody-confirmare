from flask import Flask

app = Flask(__name__)

@app.route('/confirmare/<cod>')
def confirmare(cod):
    return f"Ședința a fost confirmată! Cod: {cod}"

if __name__ == '__main__':
    app.run()