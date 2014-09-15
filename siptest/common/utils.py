from hashlib import md5


def digest_cal_cha1(
        pszAlg,
        pszUserName,
        pszRealm,
        pszPassword,
        pszNonce,
        pszCNonce,
        ):
    m = md5()
    m.update(bytes(pszUserName, 'utf8'))
    m.update(bytes(":", 'utf8'))
    m.update(bytes(pszRealm, 'utf8'))
    m.update(bytes(":", 'utf8'))
    m.update(bytes(pszPassword, 'utf8'))
    return m.hexdigest()


def digest_calc_response(
        HA1,
        pszNonce,
        pszNonceCount,
        pszCNonce,
        pszQop,
        pszMethod,
        pszDigestUri,
        pszHEntity,
        ):
    m = md5()
    m.update(bytes(pszMethod, 'utf8'))
    m.update(bytes(":", 'utf8'))
    m.update(bytes(pszDigestUri, 'utf8'))
    HA2 = m.hexdigest()

    m = md5()
    m.update(bytes(HA1, 'utf8'))
    m.update(bytes(":", 'utf8'))
    m.update(bytes(pszNonce, 'utf8'))
    m.update(bytes(":", 'utf8'))
    if pszNonceCount and pszCNonce: # pszQop:
        m.update(bytes(pszNonceCount, 'utf8'))
        m.update(bytes(":", 'utf8'))
        m.update(bytes(pszCNonce, 'utf8'))
        m.update(bytes(":", 'utf8'))
        m.update(bytes(pszQop, 'utf8'))
        m.update(bytes(":", 'utf8'))
    m.update(bytes(HA2, 'utf8'))
    hash = m.hexdigest()
    return hash

def digest_cal_cha1_2(
        pszAlg,
        pszUserName,
        pszRealm,
        pszPassword,
        pszNonce,
        pszCNonce,
        ):
    m = md5()
    m.update(pszUserName)
    m.update(":")
    m.update(pszRealm)
    m.update(":")
    m.update(pszPassword)
    return m.hexdigest()


def digest_calc_response_2(
        HA1,
        pszNonce,
        pszNonceCount,
        pszCNonce,
        pszQop,
        pszMethod,
        pszDigestUri,
        pszHEntity,
        ):
    m = md5()
    m.update(pszMethod)
    m.update(":")
    m.update(pszDigestUri)
    HA2 = m.hexdigest()

    m = md5()
    m.update(HA1)
    m.update(":")
    m.update(pszNonce)
    m.update(":")
    if pszNonceCount and pszCNonce: # pszQop:
        m.update(pszNonceCount)
        m.update(":")
        m.update(pszCNonce)
        m.update(":")
        m.update(pszQop)
        m.update(":")
    m.update(HA2)
    hash = m.hexdigest()
    return hash
