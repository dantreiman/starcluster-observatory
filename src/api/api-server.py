"""A simple server for directing starcluster from another ec2 instance in our subnet."""
import argparse
from flask import Flask
from flask import jsonify
from flask import request
import schedule
import subprocess
from threading import Thread
import time

import sge
import starcluster


parser = argparse.ArgumentParser(description='Run a server which exposes the starcluster and qstat APIs.', allow_abbrev=True)
parser.add_argument('--host_ip', default='0.0.0.0', type=str, help='IP address of interface to listen on.')
parser.add_argument('--port', default=6360, type=int, help='Port to listen on.')
parser.add_argument('--cluster_name', default='dev', type=str, help='Name of the cluster to manage.')
parser.add_argument('--starcluster_config', default='/etc/starcluster/config', type=str, help='Path to starcluster config file.')
parser.add_argument('--idle_timeout', default=30, type=int, help='Shut down nodes if idle longer than this (minutes).')

args = parser.parse_args()


app = Flask(__name__)


@app.route('/status')
def cluster_status():
    try:
        uptime, nodes = starcluster.get_cluster_status(args.cluster_name)
    except subprocess.CalledProcessError as e:
        return jsonify({'status': 'error', 'error': 'An error occurred while running starcluster listclusters'})
    return jsonify({
        'status': 'ok',
        'uptime': uptime,
        'nodes': nodes
    })


@app.route('/qhost')
def qhost():
    try:
        result = sge.qhost()
    except subprocess.CalledProcessError as e:
        return jsonify({
            'status': 'error',
            'error': 'An error occurred while running qhost'
        })
    return result


@app.route('/qstat')
def qstat():
    try:
        result = sge.qstat()
    except subprocess.CalledProcessError as e:
        return jsonify({
            'status': 'error',
            'error': 'An error occurred while running qstat'
        })
    return result


@app.route('/nodes/add')
def cluster_add_node():
    instance_type = request.args.get('instance_type')
    try:
         starcluster.add_node(args.cluster_name, instance_type=instance_type)
    except subprocess.CalledProcessError as e:
        return jsonify({
            'status': 'error',
            'error': 'An error occurred while running starcluster addnode'
        })
    return jsonify({
        'status': 'ok',
    })


@app.route('/nodes/<node_alias>/remove')
def cluster_remove_node(node_alias):
    try:
        starcluster.remove_node(args.cluster_name, node_alias)
    except subprocess.CalledProcessError as e:
        return jsonify({
        'status': 'error',
        'error': 'An error occurred while running starcluster removenode'
    })
    return jsonify({
        'status': 'ok',
    })


def run_schedule():
    """Run loop for the background task scheduler thread."""
    while 1:
        schedule.run_pending()
        time.sleep(1)


_idle_hosts = {}  # Maps host name to first time (seconds) host was detected idle.
def check_idle():
    time_now = time.time()
    print('Checking for idle hosts at time %.1f.' % time_now)
    # First, check to see if any hosts are idle.
    hosts = sge.qhost()
    host_names = set([h['name'] for h in hosts if h['name'] != 'global'])
    queued_jobs, _ = sge.qstat()
    # Hosts with no jobs scheduled on them
    busy_hosts = set([j['queue_name'].split('@')[1] for j in queued_jobs])
    # Remove hosts with jobs from idle list
    for busy_host in busy_hosts:
        if busy_host in _idle_hosts:
            del _idle_hosts[busy_host]
    # Add hosts with no jobs to idle list
    idle_hosts = host_names.difference(busy_hosts)
    for host in idle_hosts:
        if host not in _idle_hosts:
            _idle_hosts[host] = time_now
    # Check if any hosts have been idle longer than idle_timeout
    hosts_to_remove = []
    for host, start_time in _idle_hosts.copy().items():
        if time_now - start_time > (args.idle_timeout * 60):
            hosts_to_remove.append(host)
            del _idle_hosts[host]
    for host in hosts_to_remove:
        try:
            starcluster.remove_node(args.cluster_name, host)
        except subprocess.CalledProcessError as e:
            print('Error auto-removing idle host %s: %s' % (host, str(e)))


if __name__ == '__main__':
    schedule.every(60).seconds.do(check_idle)
    t = Thread(target=run_schedule)
    t.start()
    app.run(host=args.host_ip, port=args.port)