"""Cluster configuration"""
from sge_queue import SGEQueue


queues = [
    SGEQueue('cpu.q', 'c5.4xlarge', {'c4.xlarge': 1, 'c5.2xlarge': 2, 'c5.4xlarge': 4, 'c5.9xlarge': 9}, max_nodes=8),
    SGEQueue('gpu.q', 'p3.2xlarge', {'p3.2xlarge': 1, 'p3.8xlarge': 4, 'p2.xlarge': 1, 'p2.8xlarge': 4}, max_nodes=4),
    SGEQueue('mem.q', 'c5.18xlarge', {'m4.16xlarge': 1, 'c5.18xlarge': 1, 'c5.24xlarge': 1}, max_nodes=3),
]

# Don't terminate a node if it is younger than this number of minutes
min_age_minutes = 30
