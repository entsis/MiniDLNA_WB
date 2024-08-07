from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from functools import wraps
import xml.etree.ElementTree as ET
import upnpclient
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(),''))

app = Flask(__name__, template_folder='templates')

app.secret_key = os.urandom(24)

USERNAME = 'admin'
PASSWORD = 'password'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def fetch_and_parse_dlna_content(device, object_id):
    try:
        content_dir_service = None
        for service in device.services:
            if 'ContentDirectory' in service.service_id:
                content_dir_service = service
                break
        
        if content_dir_service is None:
            print("Content Directory service not found.")
            return None

        result = content_dir_service.Browse(
            ObjectID=object_id,
            BrowseFlag='BrowseDirectChildren',
            Filter='*',
            StartingIndex=0,
            RequestedCount=10,
            SortCriteria=''
        )

        root = ET.fromstring(result['Result'])

        return root
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def xml_to_explorer_structure(xml_root):
    def parse_element(element):
        tag = element.tag.split('}', 1)[-1]  # Remove namespace
        parsed = {
            'type': 'folder' if tag == 'container' else 'file',
            'title': element.findtext('{http://purl.org/dc/elements/1.1/}title', default=''),
            'id': element.get('id', ''),
            'path': None
        }
        if tag == 'item':
            res_element = element.find('{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}res')
            if res_element is not None:
                original_path = res_element.text
                parsed['path'] = original_path
        
        children = list(element)
        if children:
            child_list = []
            for dc in map(parse_element, children):
                if dc['type'] == 'folder' or dc['type'] == 'file':
                    child_list.append(dc)
            parsed['children'] = child_list
        
        return parsed

    return parse_element(xml_root)

@app.route('/browse', methods=['POST'])
@login_required
def browse():
    try:
        data = request.get_json()

        if not data or 'device_url' not in data or 'ObjectID' not in data:
            return jsonify({"error": "Invalid request, 'device_url' and 'ObjectID' are required"}), 400

        device_url = data['device_url']
        object_id = data['ObjectID']

        device = upnpclient.Device(device_url)

        xml_root = fetch_and_parse_dlna_content(device, object_id)

        if xml_root is not None:
            explorer_structure = xml_to_explorer_structure(xml_root)
            return jsonify(explorer_structure)
        else:
            return jsonify({"error": "Failed to fetch or parse the XML."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return 'Invalid credentials'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
