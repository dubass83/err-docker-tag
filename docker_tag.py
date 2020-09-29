from errbot import BotPlugin, botcmd
from itertools import chain
import re
import logging

log = logging.getLogger(name='errbot.plugins.Docker_tag')

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


class Docker_tag(BotPlugin):
    """Plugin for Docker tag command"""

    def activate(self):

        if not self.config:
            # Don't allow activation until we are configured
            message = 'Docker_tag is not configured, please do so.'
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
        super(Docker_tag, self).configure(config)
        return

    def _login(self):
        username = self.config['USERNAME']
        password = self.config['PASSWORD']
        reg_url = self.config['URL']

        try:
            client = docker.DockerClient(base_url='unix://var/run/docker.sock')
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
        new_tag = args.pop(0)
        old_tag = args.pop(0)
        regestry = args.pop(0)
        full_regestry = "{}/{}".format(re.findall(r'http[s]*://(.*)', self.config['URL'])[0], regestry)

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