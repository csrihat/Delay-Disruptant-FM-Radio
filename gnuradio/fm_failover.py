#!/usr/bin/env python3
from flask import Flask
import sys

app = Flask(__name__)

# Start with FM1
active = "FM1"
if "--active" in sys.argv:
    try:
        active = sys.argv[sys.argv.index("--active") + 1]
    except:
        pass

@app.route('/switch/<receiver>', methods=['POST'])
def switch(receiver):
    global active
    if receiver in ['FM1', 'FM2']:
        old = active
        active = receiver
        print(f"SWITCH API → {old} to {receiver}")
        return f"Active receiver: {active}", 200
    return "Invalid", 400

if __name__ == '__main__':
    print(f"Simulated receiver STARTED – active = {active}")
    app.run(host='0.0.0.0', port=8080)