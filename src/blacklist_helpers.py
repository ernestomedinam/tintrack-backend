from datetime import datetime
from flask_jwt_extended import decode_token
from models import db, TokenBlacklist

def _epoch_utc_to_datetime(epoch_utc):
    """ convert epoch timestamps (as stored in jwt) into
        python datetime objects """
    return datetime.fromtimestamp(epoch_utc)

def add_token_to_database(encoded_token, identity_claim):
    """ adds a new token to blacklist table, nor revoked """
    decoded_token = decode_token(encoded_token)
    jti = decoded_token["jti"]
    token_type = decoded_token["type"]
    user_identity = decoded_token[identity_claim]
    revoked = False
    expires = _epoch_utc_to_datetime(decoded_token["exp"])

    token = TokenBlacklist(jti, token_type, user_identity, revoked, expires)
    db.session.add(token)
    db.session.commit()

def is_token_revoked(decoded_token):
    """ this method does more than check revoked field for
        token, as we are supposed to treat as revoked any
        token that we haven't created (as in stored in db) """
    jti = TokenBlacklist.query.filter_by(jti=jti).first()
    if jti:
        return token.revoked
    else:
        return True

def revoke_token(token_id, user):
    """ revokes a given token; makes no difference if given
        token is not in db because it is considered revoked as well"""
    token = TokenBlacklist.query.filter_by(id=token_id).first()
    if token:
        token.revoked = True
        db.session.commit()

def prune_database():
    """ delete expired blacklist regs """
    now = datetime.now()
    expired_tokens = TokenBlacklist.query.filter(TokenBlacklist.expires < now).all()
    for token in expired_tokens:
        db.session.delete(token)
    db.session.commit()
