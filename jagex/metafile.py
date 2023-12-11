from dataclasses import dataclass
import datetime
import json

import jwcrypto.jwt, jwcrypto.jwk

from .jwt import validate_and_decode_jwt

@dataclass
class File():
    name: str
    size: int
    attr: int

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name"),
            size=data.get("size"),
            attr=data.get("attr")
        )

@dataclass
class Padding():
    offset: int
    size: int

    @classmethod
    def from_dict(cls, data):
        return cls(
            offset=data.get("offset"),
            size=data.get("size")
        )

@dataclass
class Pieces():
    digests: list[str]
    algorithm: str
    hashPadding: bool

    @classmethod
    def from_dict(cls, data):
        return cls(
            digests=data.get("digests"),
            algorithm=data.get("algorithm"),
            hashPadding=data.get("hashPadding")
        )

@dataclass
class Metafile():
    algorithm: str
    scanTime: datetime.datetime
    version: str
    files: list[File]
    id: str
    pad: list[Padding]
    pieces: Pieces

    @classmethod
    def from_dict(cls, data):
        return cls(
            algorithm=data.get("algorithm"),
            scanTime=datetime.datetime.fromtimestamp(data.get("scanTime")),
            version=data.get("version"),
            files=[File.from_dict(file) for file in data.get("files")],
            id=data.get("id"),
            pad=[Padding.from_dict(padding) for padding in data.get("pad")],
            pieces=Pieces.from_dict(data.get("pieces"))
        )

def parse_metafile(metafile) -> Metafile:
    # Check if the metafile is a JWT
    isJWT = False
    try:
        jwt = jwcrypto.jwt.JWT(jwt=metafile.decode())
        isJWT = True
    except Exception as e:
        if str(e) != "Token format unrecognized":
            raise Exception("Failed to parse metafile as JWT: {}".format(e))

    if not isJWT:
        # Not a JWT, so it must be a JSON file
        try:
            metafile_json = json.loads(metafile)
        except Exception as e:
            raise Exception("Failed to parse metafile as JSON: {}".format(e))
    else:
        try:
            metafile_json = validate_and_decode_jwt(jwt)
        except Exception as e:
            raise Exception("Failed to validate JWT: {}".format(e))

    return Metafile.from_dict(metafile_json)
