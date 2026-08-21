"""
Configuration for TOON MCP Server.
"""

# Common abbreviations for frequently used keys
KEY_ABBREV = {
    'id': 'i',
    'name': 'n',
    'type': 't',
    'value': 'v',
    'data': 'd',
    'message': 'm',
    'status': 's',
    'timestamp': 'ts',
    'created_at': 'ca',
    'updated_at': 'ua',
    'description': 'desc',
    'properties': 'props',
    'attributes': 'attrs',
    'parameters': 'params',
    'configuration': 'cfg',
    'metadata': 'meta',
    'response': 'resp',
    'request': 'req',
    'error': 'err',
    'result': 'res',
    'content': 'cnt',
    'username': 'usr',
    'password': 'pwd',
    'email': 'eml',
    'phone': 'ph',
    'address': 'addr',
    'count': 'ct',
    'total': 'tot',
    'items': 'itms',
    'children': 'ch',
    'parent': 'par',
    'index': 'idx',
    'length': 'len',
    'size': 'sz',
    'width': 'w',
    'height': 'h',
    'position': 'pos',
    'enabled': 'en',
    'disabled': 'dis',
    'visible': 'vis',
    'hidden': 'hid',
}

# Approximate tokens per character (rough estimate for monitoring)
CHARS_PER_TOKEN = 4

# Default thresholds for token monitoring
WARN_THRESHOLD = 50000
CRITICAL_THRESHOLD = 100000
