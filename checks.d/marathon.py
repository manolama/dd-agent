# (C) Datadog, Inc. 2014-2016
# (C)  graemej <graeme.johnson@jadedpixel.com> 2014
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)


# stdlib
from urlparse import urljoin
from os import path

# 3rd party
import requests

# project
from checks import AgentCheck

import logging
log = logging.getLogger(__name__)
class Marathon(AgentCheck):

    DEFAULT_TIMEOUT = 5
    DEFAULT_GROUP_TAGS = False
    DEFAULT_TRACK_HEALTH = False
    SERVICE_CHECK_NAME = 'marathon.can_connect'

    APP_METRICS = [
        'backoffFactor',
        'backoffSeconds',
        'cpus',
        'disk',
        'instances',
        'mem',
        'taskRateLimit',
        'tasksRunning',
        'tasksStaged'
    ]
    HEALTH_METRICS_ADDED = False

    def check(self, instance):
        if 'url' not in instance:
            raise Exception('Marathon instance missing "url" value.')

        # Load values from the instance config
        url = instance['url']
        user = instance.get('user')
        password = instance.get('password')
        if user is not None and password is not None:
            auth = (user,password)
        else:
            auth = None

        instance_tags = instance.get('tags', [])
        default_timeout = self.init_config.get('default_timeout', self.DEFAULT_TIMEOUT)
        timeout = float(instance.get('timeout', default_timeout))
        group_tags = instance.get('group_tags', self.DEFAULT_GROUP_TAGS)
        track_health = instance.get('track_health', self.DEFAULT_TRACK_HEALTH)

        if track_health and not self.HEALTH_METRICS_ADDED:
            self.APP_METRICS.append('tasksHealthy')
            self.APP_METRICS.append('tasksUnhealthy')
            self.HEALTH_METRICS_ADDED = True

        # Marathon apps
        response = self.get_json(urljoin(url, "v2/apps"), timeout, auth)
        if response is not None:
            self.gauge('marathon.apps', len(response['apps']), tags=instance_tags)
            for app in response['apps']:
                if group_tags:
                    group = path.dirname(app['id'])
                    group_app = path.basename(app['id'])
                    tags = ['app_id:' + group_app, 'group:' + group, 'version:' + app['version']] + instance_tags
                else:
                    tags = ['app_id:' + app['id'], 'version:' + app['version']] + instance_tags
                for attr in self.APP_METRICS:
                    if attr in app:
                        self.gauge('marathon.' + attr, app[attr], tags=tags)

        # Number of running/pending deployments
        response = self.get_json(urljoin(url, "v2/deployments"), timeout, auth)
        if response is not None:
            self.gauge('marathon.deployments', len(response), tags=instance_tags)

    def get_json(self, url, timeout, auth):
        try:
            r = requests.get(url, timeout=timeout, auth=auth)
            r.raise_for_status()
        except requests.exceptions.Timeout:
            # If there's a timeout
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL,
                message='%s timed out after %s seconds.' % (url, timeout),
                tags = ["url:{0}".format(url)])
            raise Exception("Timeout when hitting %s" % url)

        except requests.exceptions.HTTPError:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL,
                message='%s returned a status of %s' % (url, r.status_code),
                tags = ["url:{0}".format(url)])
            raise Exception("Got %s when hitting %s" % (r.status_code, url))

        else:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK,
                tags = ["url:{0}".format(url)]
            )

        return r.json()
