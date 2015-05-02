# Copyright (c) 2015 Rackspace, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Retry/scheduler classes and logic.
"""
import datetime
import random

from oslo_config import cfg

from barbican.common import utils
from barbican import i18n as u
from barbican.model import models
from barbican.model import repositories
from barbican.openstack.common import periodic_task
from barbican.openstack.common import service
from barbican.queue import client as async_client

LOG = utils.getLogger(__name__)

retry_opt_group = cfg.OptGroup(name='retry_scheduler',
                               title='Retry/Scheduler Options')

retry_opts = [
    cfg.FloatOpt(
        'initial_delay_seconds', default=10.0,
        help=u._('Seconds (float) to wait before starting retry scheduler')),
    cfg.FloatOpt(
        'periodic_interval_max_seconds', default=10.0,
        help=u._('Seconds (float) to wait between periodic schedule events')),
]

CONF = cfg.CONF
CONF.register_group(retry_opt_group)
CONF.register_opts(retry_opts, group=retry_opt_group)


def _compute_next_periodic_interval():
    periodic_interval = (
        CONF.retry_scheduler.periodic_interval_max_seconds
    )

    # Return +- 20% of interval.
    return random.uniform(0.8 * periodic_interval, 1.2 * periodic_interval)


class PeriodicServer(service.Service):
    """Server to process retry and scheduled tasks.

    This server is an Oslo periodic-task service (see
    http://docs.openstack.org/developer/oslo-incubator/api/openstack.common
    .periodic_task.html). On a periodic basis, this server checks for tasks
    that need to be retried, and then sends them up to the RPC queue for later
    processing by a worker node.
    """
    def __init__(self, queue_resource=None):
        super(PeriodicServer, self).__init__()

        # Setting up db engine to avoid lazy initialization
        repositories.setup_database_engine_and_factory()

        # Connect to the worker queue, to send retry RPC tasks to it later.
        self.queue = queue_resource or async_client.TaskClient()

        # Start the task retry periodic scheduler process up.
        periodic_interval = (
            CONF.retry_scheduler.periodic_interval_max_seconds
        )
        self.tg.add_dynamic_timer(
            self._check_retry_tasks,
            initial_delay=CONF.retry_scheduler.initial_delay_seconds,
            periodic_interval_max=periodic_interval)

        self.order_retry_repo = repositories.get_order_retry_tasks_repository()

    def start(self):
        LOG.info("Starting the PeriodicServer")
        super(PeriodicServer, self).start()

    def stop(self, graceful=True):
        LOG.info("Halting the PeriodicServer")
        super(PeriodicServer, self).stop(graceful=graceful)

    @periodic_task.periodic_task
    def _check_retry_tasks(self):
        """Periodically check to see if tasks need to be scheduled.

        :return: Return the number of seconds to wait before invoking this
            method again.
        """
        LOG.info(u._LI("Processing scheduled retry tasks:"))

        # Retrieve tasks to retry.
        entities, _, _, total = self.order_retry_repo.get_by_create_date(
            only_at_or_before_this_date=datetime.datetime.utcnow(),
            suppress_exception=True)

        # Create RPC tasks for each retry task found.
        if total > 0:
            for task in entities:
                self._enqueue_task(task)

        # Return the next delay before this method is invoked again.
        check_again_in_seconds = _compute_next_periodic_interval()
        LOG.info(
            u._LI("Done processing '%(total)s' tasks, will check again in "
                  "'%(next)s' seconds."),
            {
                'total': total,
                'next': check_again_in_seconds
            }
        )
        return check_again_in_seconds

    def _enqueue_task(self, task):
        retry_task_name = 'N/A'
        retry_args = 'N/A'
        retry_kwargs = 'N/A'
        try:
            # Invoke queue client to place retried RPC task on queue.
            retry_task_name = task.retry_task
            retry_args = task.retry_args
            retry_kwargs = task.retry_kwargs
            retry_method = getattr(self.queue, retry_task_name)
            retry_method(*retry_args, **retry_kwargs)

            # Remove the retry record from the queue.
            task.status = models.States.ACTIVE
            self.order_retry_repo.delete_entity_by_id(task.id, None)

            repositories.commit()

            LOG.debug(
                "(Enqueued method '{0}' with args '{1}' and "
                "kwargs '{2}')".format(
                    retry_task_name, retry_args, retry_kwargs))
        except Exception:
            LOG.exception(
                u._LE(
                    "Problem enqueuing method '%(name)s' with args '%(args)s' "
                    "and kwargs '%(kwargs)s'."),
                {
                    'name': retry_task_name,
                    'args': retry_args,
                    'kwargs': retry_kwargs
                }
            )
            repositories.rollback()
        finally:
            repositories.clear()
