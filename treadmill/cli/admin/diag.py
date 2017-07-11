"""Reports memory utilization details for given container.
"""

import os

import click
import prettytable

from treadmill import psmem
from treadmill import cgutils
from treadmill import metrics
from treadmill import utils
from treadmill import cli


class PsmemProcPrettyFormatter(object):
    """Pretty table formatter for psmem processes."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('name', None, None),
            ('tgid', None, None),
            ('threads', None, None),
            ('private', None, None),
            ('shared', None, None),
            ('total', None, None),
        ]

        format_item = cli.make_dict_to_table(schema)
        format_list = cli.make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)
        else:
            return format_item(item)

class PsmemTotalPrettyFormatter(object):
    """Pretty table formatter for psmem processes."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('memory-type', None, None),
            ('value', None, None),
        ]

        format_list = cli.make_list_to_table(schema, False)

        return format_list(item)


def init():
    """Top level command handler."""

    @click.group()
    def diag():
        """Local node and container diagnostics."""
        pass

    @diag.command(name='psmem')
    @click.option('--fast', is_flag=True, help='Disable statm/pss analysis.')
    @click.option('-v', '--verbose', is_flag=True, help='Verbose')
    @click.option('--percent', is_flag=True)
    @click.argument('app')
    def psmem_cmd(fast, app, verbose, percent):
        """Reports memory utilization details for given container."""
        if app.find('#') == -1:
            raise click.BadParameter('Specify full instance name: xxx#nnn')
        app = app.replace('#', '-')

        cgroup = None
        apps = os.listdir('/sys/fs/cgroup/memory/treadmill/apps')
        for entry in apps:
            if app in entry:
                cgroup = os.path.join('/treadmill/apps', entry)
        if not cgroup:
            raise click.BadParameter('Could not find corresponding cgroup')

        pids = cgutils.pids_in_cgroup('memory', cgroup)

        use_pss = not fast
        memusage = psmem.get_memory_usage(pids, verbose, use_pss=use_pss)

        total = sum([info['total'] for info in memusage])

        readable = lambda value: utils.bytes_to_readable(value, power='B')
        percentage = lambda value, total: "{:.1%}".format(value / total)

        to_format = ['private', 'shared', 'total']
        for info in memusage:
            for key, val in info.items():
                if key in to_format:
                    if percent:
                        info[key] = percentage(val, total)
                    else:
                        info[key] = readable(val)

        proc_table = PsmemProcPrettyFormatter()
        print(proc_table.format(memusage))

        metric = metrics.read_memory_stats(cgroup)

        total_list = []
        # Actual memory usage is without the disk cache
        total_list.append({'memory-type': 'usage', 'value':
                           readable(metric['memory.usage_in_bytes'] -
                                    metric['memory.stats']['cache'])})
        total_list.append({'memory-type': '', 'value':
                           percentage(metric['memory.usage_in_bytes'],
                                      metric['memory.limit_in_bytes'])})
        total_list.append({'memory-type': 'diskcache', 'value':
                           readable(metric['memory.stats']['cache'])})
        total_list.append({'memory-type': 'softlimit', 'value':
                           readable(metric['memory.soft_limit_in_bytes'])})
        total_list.append({'memory-type': 'hardlimit', 'value':
                           readable(metric['memory.limit_in_bytes'])})

        total_table = PsmemTotalPrettyFormatter()
        print('')
        print(total_table.format(total_list))

    del psmem_cmd
    return diag
