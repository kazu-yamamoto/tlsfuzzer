# Author: Hubert Kario, (c) 2016, 2024
# Released under Gnu GPL v2.0, see LICENSE file for details

from __future__ import print_function
import traceback
import sys
import getopt
from itertools import chain
from random import sample

from tlsfuzzer.runner import Runner
from tlsfuzzer.messages import Connect, ClientHelloGenerator, \
        ClientKeyExchangeGenerator, ChangeCipherSpecGenerator, \
        FinishedGenerator, ApplicationDataGenerator, AlertGenerator, \
        fuzz_message
from tlsfuzzer.expect import ExpectServerHello, ExpectCertificate, \
        ExpectServerHelloDone, ExpectChangeCipherSpec, ExpectFinished, \
        ExpectAlert, ExpectApplicationData, ExpectClose, \
        ExpectServerKeyExchange

from tlslite.constants import CipherSuite, AlertLevel, AlertDescription, \
        GroupName, ExtensionType, SignatureAlgorithm, HashAlgorithm
from tlslite.extensions import SupportedGroupsExtension, \
        SignatureAlgorithmsExtension, SignatureAlgorithmsCertExtension
from tlsfuzzer.utils.lists import natural_sort_keys
from tlsfuzzer.helpers import AutoEmptyExtension


version = 4


def help_msg():
    print("Usage: <script-name> [-h hostname] [-p port] [[probe-name] ...]")
    print(" -h hostname    name of the host to run the test against")
    print("                localhost by default")
    print(" -p port        port number to use for connection, 4433 by default")
    print(" probe-name     if present, will run only the probes with given")
    print("                names and not all of them, e.g \"sanity\"")
    print(" -e probe-name  exclude the probe from the list of the ones run")
    print("                may be specified multiple times")
    print(" -x probe-name  expect the probe to fail. When such probe passes despite being marked like this")
    print("                it will be reported in the test summary and the whole script will fail.")
    print("                May be specified multiple times.")
    print(" -X message     expect the `message` substring in exception raised during")
    print("                execution of preceding expected failure probe")
    print("                usage: [-x probe-name] [-X exception], order is compulsory!")
    print(" -n num         run 'num' or all(if 0) tests instead of default(500)")
    print("                (excluding \"sanity\" tests)")
    print(" -d             negotiate ECDHE-RSA instead of RSA key exchange, send")
    print("                additional extensions")
    print(" -C ciph        Use specified ciphersuite. Either numerical value or")
    print("                IETF name.")
    print(" -M | --ems     Advertise support for Extended Master Secret")
    print(" --help         this message")


def main():
    host = "localhost"
    port = 4433
    num_limit = 500
    run_exclude = set()
    expected_failures = {}
    last_exp_tmp = None
    dhe = False
    ciphers = None
    ems = False

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "h:p:e:x:X:n:dC:M", ["help", "ems"])
    for opt, arg in opts:
        if opt == '-h':
            host = arg
        elif opt == '-p':
            port = int(arg)
        elif opt == '-e':
            run_exclude.add(arg)
        elif opt == '-x':
            expected_failures[arg] = None
            last_exp_tmp = str(arg)
        elif opt == '-X':
            if not last_exp_tmp:
                raise ValueError("-x has to be specified before -X")
            expected_failures[last_exp_tmp] = str(arg)
        elif opt == '-n':
            num_limit = int(arg)
        elif opt == '-d':
            dhe = True
        elif opt == '-C':
            if arg[:2] == '0x':
                ciphers = [int(arg, 16)]
            else:
                try:
                    ciphers = [getattr(CipherSuite, arg)]
                except AttributeError:
                    ciphers = [int(arg)]
        elif opt == '-M' or opt == '--ems':
            ems = True
        elif opt == '--help':
            help_msg()
            sys.exit(0)
        else:
            raise ValueError("Unknown option: {0}".format(opt))

    if args:
        run_only = set(args)
    else:
        run_only = None

    if ciphers:
        if not dhe:
            # by default send minimal set of extensions, but allow user
            # to override it
            dhe = ciphers[0] in CipherSuite.ecdhAllSuites or \
                    ciphers[0] in CipherSuite.dhAllSuites
    else:
        if dhe:
            ciphers = [CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA]
        else:
            ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA]

    conversations = {}

    conversation = Connect(host, port)
    node = conversation
    ext = {}
    if ems:
        ext[ExtensionType.extended_master_secret] = AutoEmptyExtension()
    if dhe:
        groups = [GroupName.secp256r1,
                  GroupName.ffdhe2048]
        ext[ExtensionType.supported_groups] = SupportedGroupsExtension()\
            .create(groups)
        # because we're fuzzing, we need consistent lengths, so
        # hardcode values
        sig_algs = [
            (x, y) for x in
            [HashAlgorithm.sha1,
             HashAlgorithm.sha256,
             HashAlgorithm.sha384,
             HashAlgorithm.sha512]
            for y in
            [SignatureAlgorithm.ecdsa,
             SignatureAlgorithm.rsa]
        ]
        ext[ExtensionType.signature_algorithms] = \
            SignatureAlgorithmsExtension().create(sig_algs)
        ext[ExtensionType.signature_algorithms_cert] = \
            SignatureAlgorithmsCertExtension().create(sig_algs)
    ext_renego_info = dict(ext)
    if not ext:
        ext = None
    ext_renego_info[ExtensionType.renegotiation_info] = None
    node = node.add_child(ClientHelloGenerator(
        ciphers + [CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV],
        version=(3, 3), extensions=ext))
    srv_ext = {ExtensionType.renegotiation_info:None}
    if ems:
        srv_ext[ExtensionType.extended_master_secret] = None
    node = node.add_child(ExpectServerHello(extensions=srv_ext))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    conversations["sanity"] = conversation

    conversation = Connect(host, port)
    node = conversation
    node = node.add_child(ClientHelloGenerator(ciphers, version=(3, 3),
                                               extensions=ext_renego_info))
    srv_ext = {ExtensionType.renegotiation_info:None}
    if ems:
        srv_ext[ExtensionType.extended_master_secret] = None
    node = node.add_child(ExpectServerHello(extensions=srv_ext))
    node = node.add_child(ExpectCertificate())
    if dhe:
        node = node.add_child(ExpectServerKeyExchange())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    conversations["sanity w/ext"] = conversation

    # test different message types for client hello
    for i in range(1, 0x100):
        conversation = Connect(host, port)
        node = conversation
        hello_gen = ClientHelloGenerator(
            ciphers + [CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV],
            version=(3, 3),
            extensions=ext)
        node = node.add_child(fuzz_message(hello_gen, xors={0: i}))
        node = node.add_child(ExpectAlert())
        node = node.add_child(ExpectClose())
        conversations["Client Hello type fuzz to {0}".format(1 ^ i)] = conversation

    # test invalid sizes for session ID length
    if not ext:
        for i in range(1, 0x100):
            conversation = Connect(host, port)
            node = conversation
            hello_gen = ClientHelloGenerator(
                ciphers + [CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV],
                version=(3, 3), extensions=ext)
            node = node.add_child(fuzz_message(hello_gen, substitutions={38: i}))
            node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                              description=AlertDescription.decode_error))
            node = node.add_child(ExpectClose())
            conversations["session ID len fuzz to {0}".format(i)] = conversation

    for i in range(1, 0x100):
        conversation = Connect(host, port)
        node = conversation
        hello_gen = ClientHelloGenerator(ciphers, version=(3, 3),
                                         extensions=ext_renego_info)
        node = node.add_child(fuzz_message(hello_gen, substitutions={38: i}))
        node = node.add_child(ExpectAlert())
        node = node.add_child(ExpectClose())
        conversations["session ID len fuzz to {0} w/ext".format(i)] = conversation


    # test invalid sizes for cipher suites length
    if not ext:
        for i in range(1, 0x100):
            conversation = Connect(host, port)
            node = conversation
            hello_gen = ClientHelloGenerator(
                ciphers + [CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV],
                version=(3, 3), extensions=ext)
            node = node.add_child(fuzz_message(hello_gen, xors={40: i}))
            node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                              description=AlertDescription.decode_error))
            node = node.add_child(ExpectClose())
            conversations["cipher suites len fuzz to {0}".format(4 ^ i)] = conversation

        for i in (1, 2, 4, 8, 16, 128, 254, 255):
            for j in range(0, 0x100):
                conversation = Connect(host, port)
                node = conversation
                hello_gen = ClientHelloGenerator(
                    ciphers + [CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV],
                    version=(3, 3), extensions=ext)
                node = node.add_child(fuzz_message(hello_gen, substitutions={39: i, 40: j}))
                node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                                  description=AlertDescription.decode_error))
                node = node.add_child(ExpectClose())
                conversations["cipher suites len fuzz to {0}".format((i<<8) + j)] = conversation

    for i in range(1, 0x100):
        # create valid extension-less ClientHellos
        if dhe and not ems and i == 56:
            continue
        if dhe and ems and i == 60:
            continue
        conversation = Connect(host, port)
        node = conversation
        hello_gen = ClientHelloGenerator(ciphers, version=(3, 3),
                                         extensions=ext_renego_info)
        node = node.add_child(fuzz_message(hello_gen, xors={40: i}))
        node = node.add_child(ExpectAlert(level=AlertLevel.fatal))
#        node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
#                                          description=AlertDescription.decode_error))
        node = node.add_child(ExpectClose())
        conversations["cipher suites len fuzz to {0} w/ext".format(4 ^ i)] = conversation

    for i in (1, 2, 4, 8, 16, 128, 254, 255):
        for j in range(0, 0x100):
            conversation = Connect(host, port)
            node = conversation
            hello_gen = ClientHelloGenerator(ciphers, version=(3, 3),
                                             extensions=ext_renego_info)
            node = node.add_child(fuzz_message(hello_gen, substitutions={39: i, 40: j}))
            node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                              description=AlertDescription.decode_error))
            node = node.add_child(ExpectClose())
            conversations["cipher suites len fuzz to {0} w/ext".format((i<<8) + j)] = conversation

    # test invalid sizes for compression methods
    if not ext:
        for i in range(1, 0x100):
            conversation = Connect(host, port)
            node = conversation
            hello_gen = ClientHelloGenerator(
                ciphers + [CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV],
                version=(3, 3), extensions=ext)
            node = node.add_child(fuzz_message(hello_gen, xors={45: i}))
            node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                              description=AlertDescription.decode_error))
            node = node.add_child(ExpectClose())
            conversations["compression methods len fuzz to {0}".format(1 ^ i)] = conversation

    for i in range(1, 0x100):
        if not dhe and not ems and 1 ^ i == 8:  # this length creates a valid extension-less hello
            continue
        if dhe and not ems and 1 ^ i == 62:
            continue
        if dhe and ems and 1 ^ i == 66:
            continue
        if not dhe and ems and 1 ^ i == 12:
            continue
        conversation = Connect(host, port)
        node = conversation
        hello_gen = ClientHelloGenerator(ciphers, version=(3, 3),
                                         extensions=ext_renego_info)
        node = node.add_child(fuzz_message(hello_gen, xors={43: i}))
        node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                          description=AlertDescription.decode_error))
        node = node.add_child(ExpectClose())
        conversations["compression methods len fuzz to {0} w/ext".format(1 ^ i)] = conversation

    # test invalid sizes for extensions
    for i in range(1, 0x100):
        conversation = Connect(host, port)
        node = conversation
        hello_gen = ClientHelloGenerator(ciphers, version=(3, 3),
                                         extensions=ext_renego_info)
        node = node.add_child(fuzz_message(hello_gen, xors={46: i}))
        node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                          description=AlertDescription.decode_error))
        node = node.add_child(ExpectClose())
        conversations["extensions len fuzz to {0}".format(5 ^ i)] = conversation

    for i in (1, 2, 4, 8, 16, 254, 255):
        for j in range(0, 0x100):
            conversation = Connect(host, port)
            node = conversation
            hello_gen = ClientHelloGenerator(ciphers, version=(3, 3),
                                             extensions=ext_renego_info)
            node = node.add_child(fuzz_message(hello_gen, substitutions={45: i, 46: j}))
            node = node.add_child(ExpectAlert(level=AlertLevel.fatal,
                                              description=AlertDescription.decode_error))
            node = node.add_child(ExpectClose())
            conversations["extensions len fuzz to {0}".format((i<<8)+j)] = conversation

    # run the conversation
    good = 0
    bad = 0
    xfail = 0
    xpass = 0
    failed = []
    xpassed = []
    if not num_limit:
        num_limit = len(conversations)

    # make sure that sanity test is run first and last
    # to verify that server was running and kept running throughout
    sanity_tests = [('sanity', conversations['sanity'])]
    if run_only:
        if num_limit > len(run_only):
            num_limit = len(run_only)
        regular_tests = [(k, v) for k, v in conversations.items() if k in run_only]
    else:
        regular_tests = [(k, v) for k, v in conversations.items() if
                         (k != 'sanity') and k not in run_exclude]
    sampled_tests = sample(regular_tests, min(num_limit, len(regular_tests)))
    ordered_tests = chain(sanity_tests, sampled_tests, sanity_tests)

    for c_name, c_test in ordered_tests:
        print("{0} ...".format(c_name))

        runner = Runner(c_test)

        res = True
        exception = None
        try:
            runner.run()
        except Exception as exp:
            exception = exp
            print("Error while processing")
            print(traceback.format_exc())
            res = False

        if c_name in expected_failures:
            if res:
                xpass += 1
                xpassed.append(c_name)
                print("XPASS-expected failure but test passed\n")
            else:
                if expected_failures[c_name] is not None and  \
                    expected_failures[c_name] not in str(exception):
                        bad += 1
                        failed.append(c_name)
                        print("Expected error message: {0}\n"
                            .format(expected_failures[c_name]))
                else:
                    xfail += 1
                    print("OK-expected failure\n")
        else:
            if res:
                good += 1
                print("OK\n")
            else:
                bad += 1
                failed.append(c_name)

    print("Test end")
    print(20 * '=')
    print("version: {0}".format(version))
    print(20 * '=')
    print("TOTAL: {0}".format(len(sampled_tests) + 2*len(sanity_tests)))
    print("SKIP: {0}".format(len(run_exclude.intersection(conversations.keys()))))
    print("PASS: {0}".format(good))
    print("XFAIL: {0}".format(xfail))
    print("FAIL: {0}".format(bad))
    print("XPASS: {0}".format(xpass))
    print(20 * '=')
    sort = sorted(xpassed ,key=natural_sort_keys)
    if len(sort):
        print("XPASSED:\n\t{0}".format('\n\t'.join(repr(i) for i in sort)))
    sort = sorted(failed, key=natural_sort_keys)
    if len(sort):
        print("FAILED:\n\t{0}".format('\n\t'.join(repr(i) for i in sort)))

    if bad or xpass:
        sys.exit(1)

if __name__ == "__main__":
    main()
