from gevent import monkey; monkey.patch_all()  # need to patch sockets to make requests async
from gevent.pywsgi import WSGIServer
import time
from flask import Flask, Response, request, jsonify, abort

import requests

CHUNK_SIZE = 1024*1024  # bytes

app = Flask(__name__)

# URL format: <protocol>://<username>:<password>@<hostname>:<port>, example: https://test:1234@localhost:9981
config = {
    'tvhURL': 'http://test:test@127.0.0.1:9981',
    'tvhProxyURL': 'http://127.0.0.1',
    'tvhProxyPort': 5004,  # do _NOT_ change this.
    'tunerCount': 6,  # number of tuners in tvh
    'tvhWeight': 300 # subscription priority
}


@app.route('/discover.json')
def discover():
    return jsonify({
        'FriendlyName': 'tvhProxy',
        'ModelNumber': 'HDTC-2US',
        'FirmwareName': 'hdhomeruntc_atsc',
        'TunerCount': config['tunerCount'],
        'FirmwareVersion': '20150826',
        'DeviceID': '12345678',
        'DeviceAuth': 'test1234',
        'BaseURL': '%s:%s' % (config['tvhProxyURL'], config['tvhProxyPort']),
        'LineupURL': '%s:%s/lineup.json' % (config['tvhProxyURL'], config['tvhProxyPort'])
    })


@app.route('/lineup_status.json')
def status():
    return jsonify({
        'ScanInProgress': 0,
        'ScanPossible': 1,
        'Source': "Cable",
        'SourceList': ['Cable']#, 'Antenna']
    })


@app.route('/lineup.json')
def lineup():
    lineup = []

    for c in _get_channels():
        if c['enabled']:
            url = '%s/auto/v%s' % (config['tvhProxyURL'], c['number'])

            lineup.append({'GuideNumber': str(c['number']),
                           'GuideName': c['name'],
                           'URL': url
                           })

    return jsonify(lineup)


@app.route('/auto/<channel>')
def stream(channel):
    url = ''
    channel = channel.replace('v', '')
    duration = request.args.get('duration', default=0, type=int)

    if not duration == 0:
        duration += time.time()

    for c in _get_channels():
        if str(c['number']) == channel:
            url = '%s/stream/channel/%s?weight=%s' % (config['tvhURL'], c['uuid'], config['tvhWeight'])

    if not url:
        abort(404)
    else:
        req = requests.get(url, stream=True)

        def generate():
            yield ''
            for chunk in req.iter_content(chunk_size=CHUNK_SIZE):
                if not duration == 0 and not time.time() < duration:
                    req.close()
                    break
                yield chunk

        return Response(generate(), content_type=req.headers['content-type'], direct_passthrough=True)


def _get_channels():
    url = '%s/api/channel/grid?start=0&limit=999999' % config['tvhURL']

    try:
        r = requests.get(url)
        return r.json()['entries']

    except Exception as e:
        print('An error occured: ' + repr(e))


if __name__ == '__main__':
    http = WSGIServer(('', config['tvhProxyPort']), app.wsgi_app)
    http.serve_forever()

#    app.run(port=config['tvhProxyPort'], host='0.0.0.0', threaded=True)
