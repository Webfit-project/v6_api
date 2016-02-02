from base64 import b64encode, b64decode
from pyramid.httpexceptions import HTTPBadRequest

import hmac
import hashlib
import requests
import urllib.error

from urllib.parse import parse_qs

from pydiscourse.client import DiscourseClient

import logging
log = logging.getLogger(__name__)


# 10 seconds timeout for requests to discourse API
# Using a large value to take into account a possible slow restart (caching)
# of discourse.
CLIENT_TIMEOUT = 10


def decode_payload(payload):
    decoded = b64decode(payload.encode('utf-8')).decode('utf-8')
    assert 'nonce' in decoded
    assert len(payload) > 0
    return decoded


def check_signature(payload, signature, key):
    h = hmac.new(
        key.encode('utf-8'), payload.encode('utf-8'), digestmod=hashlib.sha256)
    this_signature = h.hexdigest()

    if this_signature != signature:
        log.error('Signature mismatch')
        raise HTTPBadRequest('discourse login failed')


def request_nonce(base_url, key, timeout):
    url = '%s/session/sso' % base_url
    try:
        r = requests.get(url, allow_redirects=False, timeout=timeout)
        assert r.status_code == 302
    except Exception:
        log.error('Could not request nonce', exc_info=True)
        return None

    location = r.headers['Location']
    parsed = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed.query)
    sso = params['sso'][0]
    sig = params['sig'][0]

    check_signature(sso, sig, key)
    payload = decode_payload(sso)
    return parse_qs(payload)['nonce'][0]


def create_response_payload(user, nonce, base_url, key):
    if not nonce:
        log.warning('No nonce, skipping discourse url creation')
        return None

    params = {
        'nonce': nonce,
        'email': user.email,
        'external_id': user.id,
        'username': user.username,
        'name': user.username,
    }

    return_payload = b64encode(
        urllib.parse.urlencode(params).encode('utf-8'))
    h = hmac.new(key.encode('utf-8'), return_payload, digestmod=hashlib.sha256)
    qs = urllib.parse.urlencode({'sso': return_payload, 'sig': h.hexdigest()})
    return '%s?%s' % (base_url, qs)


def get_nonce_from_sso(sso, sig, key):
    payload = urllib.parse.unquote(sso)
    try:
        decoded = decode_payload(payload)
    except Exception as e:
        log.error('Failed to decode payload', e)
        raise HTTPBadRequest('discourse login failed')

    check_signature(payload, sig, key)

    # Build the return payload
    qs = parse_qs(decoded)
    return qs['nonce'][0]


def discourse_redirect(user, sso, signature, settings):
    base_url = '%s/session/sso_login' % settings.get('discourse.url')
    key = str(settings.get('discourse.sso_secret'))  # must not be unicode
    nonce = get_nonce_from_sso(sso, signature, key)
    if nonce:
        return create_response_payload(user, nonce, base_url, key)
    else:
        return None


def discourse_redirect_without_nonce(user, settings):
    discourse_url = settings.get('discourse.url')
    base_url = '%s/session/sso_login' % discourse_url
    key = str(settings.get('discourse.sso_secret'))  # must not be unicode
    nonce = request_nonce(discourse_url, key, CLIENT_TIMEOUT)
    return create_response_payload(user, nonce, base_url, key)


def get_discourse_client(settings):
    api_key = settings['discourse.api_key']
    url = settings['discourse.url']
    # system is a built-in user available in all discourse instances.
    return DiscourseClient(
        url, api_username='system', api_key=api_key, timeout=CLIENT_TIMEOUT)


discourse_userid_cache = {}


def discourse_get_userid_by_userid(client, userid):
    discourse_userid = discourse_userid_cache.get(userid)
    if not discourse_userid:
        discourse_user = client.by_external_id(userid)
        discourse_userid = discourse_user['id']
        discourse_userid_cache[userid] = discourse_userid
    return discourse_userid


def discourse_sync_sso(user, settings):
    key = str(settings.get('discourse.sso_secret'))  # must not be unicode
    client = get_discourse_client(settings)
    result = client.sync_sso(
        sso_secret=key,
        name=user.username,
        username=user.username,
        email=user.email,
        external_id=user.id)
    if result:
        discourse_userid_cache[user.id] = result['id']
    return result


def discourse_logout(userid, settings):
    client = get_discourse_client(settings)
    discourse_userid = discourse_get_userid_by_userid(client, userid)
    client.log_out(discourse_userid)
    return discourse_userid