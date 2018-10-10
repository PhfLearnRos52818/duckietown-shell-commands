import argparse
import datetime
import subprocess

from dt_shell import DTCommandAbs, dtslogger
from dt_shell.env_checks import get_dockerhub_username, check_docker_environment
from dt_shell.remote import dtserver_submit, get_duckietown_server_url


def tag_from_date(d):
    # YYYY-MM-DDTHH:MM:SS[.mmmmmm][+HH:MM].
    s = d.isoformat()

    s = s.replace(':', '_')
    s = s.replace('T', '_')
    s = s.replace('-', '_')
    s = s[:s.index('.')]
    return s


def build(username, challenge, do_push=True, no_cache=False):
    tag = tag_from_date(datetime.datetime.now())
    df = 'Dockerfile'
    image = '%s/%s:%s' % (username, challenge, tag)

    if not os.path.exists(df):
        msg = 'I expected to find the file "%s".' % df
        raise Exception(msg)

    cmd = ['docker', 'build', '.',
           '-t', image,
           '-f', df,
           ]

    if no_cache:
        cmd.append('--no-cache')
    print(cmd)
    p = subprocess.Popen(cmd)
    p.communicate()
    if p.returncode != 0:
        msg = 'Could not run docker build.'
        raise Exception(msg)

    if do_push:
        cmd = ['docker', 'push', image]
        p = subprocess.Popen(cmd)
        p.communicate()
        p.communicate()

        if p.returncode != 0:
            msg = 'Could not run docker push.'
            msg += '\nTry to login using "docker login".'
            raise Exception(msg)

    return image


class DTCommand(DTCommandAbs):

    @staticmethod
    def command(shell, args):
        check_docker_environment()

        token = shell.get_dt1_token()

        prog = 'dts challenges submit'
        usage = """
        

Submission:

    %(prog)s --challenge NAME



## Building options

Rebuilds ignoring Docker cache

    %(prog)s --no-cache



## Attaching user data
    
Submission with an identifying label:

    %(prog)s --user-label  "My submission"    
    
Submission with an arbitrary JSON payload:

    %(prog)s --user-meta  '{"param1": 123}'   
        

        
        
"""
        parser = argparse.ArgumentParser(prog=prog, usage=usage)

        parser.add_argument('--challenge',
                            help="Specify challenge name.")

        group = parser.add_argument_group("Submission identification")
        group.add_argument('--user-label', dest='message', action="store", nargs='+', default=None, type=str,
                           help="Submission message")
        group.add_argument('--user-meta', dest='metadata', action='store', nargs='+', default=None,
                           help="Custom JSON structure to attach to the submission")

        group = parser.add_argument_group("Building settings.")
        group.add_argument('--no-push', dest='no_push', action='store_true', default=False,
                           help="Disable pushing of container")
        group.add_argument('--no-submit', dest='no_submit', action='store_true', default=False,
                           help="Disable submission (only build and push)")
        group.add_argument('--no-cache', dest='no_cache', action='store_true', default=False)

        group.add_argument('-C', dest='cwd', default=None, help='Base directory')

        parsed = parser.parse_args(args)

        do_push = not parsed.no_push

        if parsed.cwd is not None:
            dtslogger.info('Changing to directory %s' % parsed.cwd)
            os.chdir(parsed.cwd)

        submission_label = ' '.join(parsed.message) if parsed.message is not None else None
        submission_metadata = ' '.join(parsed.metadata) if parsed.metadata is not None else None

        username = get_dockerhub_username(shell)

        if parsed.challenge:
            challenge_name = parsed.challenge

        else:
            try:
                ci = read_challenge_info('.')
                challenge_name = ci.challenge_name
            except NotFound:
                msg = 'Could not find challenge.yaml. You must use --challenge to specify a challenge name.'
                raise Exception(msg)

        hashname = build(username, challenge_name, do_push, no_cache=parsed.no_cache)

        data = {'hash': hashname, 'user_label': submission_label, 'user_payload': submission_metadata}

        if not parsed.no_submit:
            submission_id = dtserver_submit(token, challenge_name, data)
            print('Successfully created submission %s' % submission_id)
            print('')
            url = get_duckietown_server_url() + '/humans/submissions/%s' % submission_id
            print('You can track the progress at: %s' % url)

            print('')
            print('You can also use the command:')
            print('')
            print('   dts challenges follow --submission %s' % submission_id)


# FIXME: repeated code - because no robust way to have imports in duckietown-shell-commands


def find_conf_file(d, fn0):
    print d, fn0
    fn = os.path.join(d, fn0)
    if os.path.exists(fn):
        return fn
    else:
        d0 = os.path.dirname(d)
        if not d0 or d0 == '/':
            msg = 'Could not find file %r' % fn0
            raise NotFound(msg)
        return find_conf_file(d0, fn0)


class NotFound(Exception):
    pass


class ChallengeInfoLocal:
    def __init__(self, challenge_name):
        self.challenge_name = challenge_name


def read_challenge_info(dirname):
    bn = 'challenge.yaml'
    dirname = os.path.realpath(dirname)
    fn = find_conf_file(dirname, bn)

    data = read_yaml_file(fn)
    try:
        challenge_name = data['challenge']
        return ChallengeInfoLocal(challenge_name)
    except Exception as e:
        msg = 'Could not read file %r: %s' % (fn, e)
        raise NotFound(msg)


import os

# noinspection PyUnresolvedReferences
import ruamel.ordereddict as s
from ruamel import yaml


def read_yaml_file(fn):
    if not os.path.exists(fn):
        msg = 'File does not exist: %s' % fn
        raise Exception(msg)

    with open(fn) as f:
        data = f.read()

        try:
            return yaml.load(data, Loader=yaml.Loader)
        except Exception as e:
            msg = 'Could not read YAML file %s:\n\n%s' % (fn, e)
            raise Exception(msg)
