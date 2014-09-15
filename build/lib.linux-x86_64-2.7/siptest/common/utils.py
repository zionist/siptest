from hashlib import md5
import socket
from multiprocessing import Process
import logging


def run_sender(options, num, sender_factory):
    logger = logging.getLogger()
    logger.debug("Run sender")
    sender_factory.run(num)
    print(sender_factory.successes)


def run_receiver(options, num, receiver_factory):
    logger = logging.getLogger()
    logger.debug("Run receiver")
    receiver_factory.run(num)
    print(receiver_factory.successes)


# {workder id: clients array}
def make_processes(clients, options, run_func):
    logger = logging.getLogger()
    # logger.info(clients)
    procs = []
    num = 0
    for client in clients:
        proc = Process(target=run_func, args=(options, num, client,))
        proc.daemon = False
        procs.append(proc)
        num += 1
    logger.info("Make %s processes" % len(procs))
    return procs


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

