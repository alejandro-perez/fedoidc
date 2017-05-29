import time
from urllib.parse import quote_plus, urlparse
from urllib.parse import unquote_plus

from fedoidc.test_utils import MetaDataStore

from fedoidc.bundle import FSJWKSBundle
from oic.utils.keyio import build_keyjar

from fedoidc import test_utils, MetadataStatement
from fedoidc.operator import FederationOperator
from fedoidc.operator import Operator

KEYDEFS = [
    {"type": "RSA", "key": '', "use": ["sig"]},
    {"type": "EC", "crv": "P-256", "use": ["sig"]}
]

TOOL_ISS = 'https://localhost'

FO = {'swamid': 'https://swamid.sunet.se', 'feide': 'https://www.feide.no',
      'edugain': 'https://edugain.com'}

OA = {'sunet': 'https://sunet.se'}

IA = {}

SMS_DEF = {
    OA['sunet']: {
        "discovery": {
            FO['swamid']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['swamid']},
            ]
        },
        "registration": {
            FO['swamid']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'registration'},
                 'signer': FO['swamid']},
            ]
        }
    }
}

SMSU_DEF = {
    OA['sunet']: {
        "discovery": {
            FO['feide']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['feide']},
            ],
            FO['edugain']: [
                {'request': {}, 'requester': FO['swamid'],
                 'signer_add': {'federation_usage': 'discovery'},
                 'signer': FO['edugain']},
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {}, 'signer': FO['swamid']}
            ]
        },
        "registration": {
            FO['feide']: [
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {'federation_usage': 'registration'},
                 'signer': FO['feide']},
            ],
            FO['edugain']: [
                {'request': {}, 'requester': FO['swamid'],
                 'signer_add': {'federation_usage': 'response'},
                 'signer': FO['edugain']},
                {'request': {}, 'requester': OA['sunet'],
                 'signer_add': {}, 'signer': FO['swamid']}
            ]
        },
    }
}

liss = list(FO.values())
liss.extend(list(OA.values()))

signer, keybundle = test_utils.setup(
    KEYDEFS, TOOL_ISS, liss, csms_def=SMS_DEF, ms_path='ms_dir',
    csmsu_def=SMSU_DEF, mds_dir='mds', base_url='https://localhost')


class Response(object):
    pass


class MockHTTPClient():
    def __init__(self, mds):
        self.mds = mds

    def http_request(self, url):
        p = urlparse(url)
        rsp = Response()
        rsp.status_code = 200
        rsp.text = self.mds[p.path.split('/')[-1]]
        return rsp


def test_key_rotation():
    _keyjar = build_keyjar(KEYDEFS)[1]
    fo = FederationOperator(iss='https://example.com/op', keyjar=_keyjar,
                            keyconf=KEYDEFS, remove_after=1)
    fo.rotate_keys()
    assert len(fo.keyjar.get_issuer_keys('')) == 4
    time.sleep(1)
    fo.rotate_keys()
    assert len(fo.keyjar.get_issuer_keys('')) == 4


def test_unpack_metadata_statement():
    s = signer[OA['sunet']]
    req = MetadataStatement(issuer='https://example.org/op')
    ms = s.create_signed_metadata_statement(req, 'discovery')

    jb = FSJWKSBundle('', None, 'fo_jwks',
                      key_conv={'to': quote_plus, 'from': unquote_plus})

    mds = MetaDataStore('mds')
    op = Operator(jwks_bundle=jb)
    op.httpcli = MockHTTPClient(mds)
    res = op.unpack_metadata_statement(jwt_ms=ms)
    assert len(res.parsed_statement) == 3
    loel = op.evaluate_metadata_statement(res.result)
    assert len(loel) == 3
    assert set([l.fo for l in loel]) == {'https://swamid.sunet.se',
                                          'https://www.feide.no',
                                          'https://edugain.com'}