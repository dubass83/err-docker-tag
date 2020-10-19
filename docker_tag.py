from errbot import BotPlugin, botcmd
from itertools import chain
import re
import logging
import time

log = logging.getLogger(name='errbot.plugins.DockerTag')

try:
    import docker
except ImportError:
    log.error("Please install 'docker' python package")

try:
    from config import DOCKER_REG_URL, DOCKER_USERNAME, DOCKER_PASSWORD
except ImportError:
    # Default mandatory configuration
    DOCKER_REG_URL = ''
    DOCKER_USERNAME = ''
    DOCKER_PASSWORD = ''

CONFIG_TEMPLATE = {
    'URL': DOCKER_REG_URL,
    'USERNAME': DOCKER_USERNAME,
    'PASSWORD': DOCKER_PASSWORD
}


class DockerTag(BotPlugin):
    """Plugin for Docker tag command"""

    def activate(self):

        if not self.config:
            # Don't allow activation until we are configured
            message = 'DockerTag is not configured, please do so.'
            self.log.info(message)
            self.warn_admins(message)
            return

        self.registry_connect = self._login()
        if self.registry_connect:
            super().activate()

    def get_configuration_template(self):
        """ configuration entries """
        return CONFIG_TEMPLATE

    def configure(self, configuration):
        if configuration is not None and configuration != {}:
            config = dict(chain(CONFIG_TEMPLATE.items(),
                                configuration.items()))
        else:
            config = CONFIG_TEMPLATE
        super(DockerTag, self).configure(config)
        return

    def _login(self):
        username = self.config['USERNAME']
        password = self.config['PASSWORD']
        reg_url = self.config['URL']

        try:
            client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        except docker.errors.APIError:
            message = 'Unable connect to socket unix://var/run/docker.sock'
            self.log.error(message)
            return False

        try:
            self.log.debug('try login USER {} to registry {}'.format(username, reg_url))
            client.login(username=username, password=password, registry=reg_url) 
            self.log.info('logging into {}'.format(reg_url))
            return client
        except docker.errors.APIError:
            message = 'Unable to login to {}'.format(reg_url)
            self.log.error(message)
            return False

    @botcmd(split_args_with=' ')
    def dt_set(self, msg, args):
        """
        Set new tag for docker image.

        Example:
        !dt_set gc-web/data-container stage-0.1.1 prod-0.0.1
        """
        regestry = args.pop(0)
        old_tag = args.pop(0)
        new_tag = args.pop(0)
        full_regestry = "{}/{}".format(re.findall(r'http[s]*://(.*)', self.config['URL'])[0], regestry)
        self.log.debug("Get params new_tag: {} old_tag: {} regestry: {}".format(
            new_tag,
            old_tag,
            regestry
        ))
        client = self.registry_connect

        try:
            # pull docker image from registry
            image = client.images.pull('{}:{}'.format(full_regestry, old_tag))
            # set new tag
            if not image.tag(full_regestry, tag=new_tag):
                message = 'Unable to set new tag {} for {}:{}'.format(new_tag, full_regestry, old_tag)
                self.log.error(message)
                return False
            # push new tag to registry
            for line in client.images.push(full_regestry, tag=new_tag, stream=True, decode=True):
                # print(line)
                self.log.info(line)

            # sleep for 5 second
            time.sleep(5)

            # tag and push release tag which trigger codepipeline build
            if not image.tag(full_regestry, tag="release"):
                message = 'Unable to set new tag {} for {}:{}'.format("release", full_regestry, old_tag)
                self.log.error(message)
                return False
            for line in client.images.push(full_regestry, tag="release", stream=True, decode=True):
                # print(line)
                self.log.info(line)

            response = 'New tag - {0} pushed on the {1} registry for tag - {2}'.format(
                new_tag,
                full_regestry,
                old_tag
            )
        except docker.errors.APIError:
            response = 'Have Problem with Docker tag - {0}.'.format(old_tag)

        self.send(msg.frm,
                  response,
                  in_reply_to=msg,
                  groupchat_nick_reply=True)
