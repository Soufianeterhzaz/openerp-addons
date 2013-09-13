# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-Today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

import logging

from openerp import tools
from openerp.addons.mail.mail_thread import decode_header
from openerp.osv import osv

_logger = logging.getLogger(__name__)


class MailThread(osv.Model):
    """ Update MailThread to add the feature of bounced emails and replied emails
    in message_process. """
    _name = 'mail.thread'
    _inherit = ['mail.thread']

    def message_route_check_bounce(self, cr, uid, message, context=None):
        bounce_alias = self.pool['ir.config_parameter'].get_param(cr, uid, "mail.bounce.alias", context=context)
        message_id = message.get('Message-Id')
        email_from = decode_header(message, 'From')
        email_to = decode_header(message, 'To')

        # 0. Verify whether this is a bounced email (wrong destination,...) -> use it to collect data, such as dead leads
        if bounce_alias in email_to:
            bounce_match = tools.bounce_re.search(email_to)
            if bounce_match:
                bounced_mail_id = bounce_match.group(1)
                self.pool['mail.mail'].set_bounced(cr, uid, [bounced_mail_id], context=context)
                if self.pool['mail.mail'].exists(cr, uid, bounced_mail_id):
                    mail = self.pool['mail.mail'].browse(cr, uid, bounced_mail_id, context=context)
                    bounced_model = mail.model
                    bounced_thread_id = mail.res_id
                else:
                    bounced_model = bounce_match.group(2)
                    bounced_thread_id = int(bounce_match.group(3)) if bounce_match.group(3) else 0
                _logger.info('Routing mail from %s to %s with Message-Id %s: bounced mail from mail %s, model: %s, thread_id: %s',
                             email_from, email_to, message_id, bounced_mail_id, bounced_model, bounced_thread_id)
                if bounced_model and bounced_model in self.pool and hasattr(self.pool[bounced_model], 'message_receive_bounce'):
                    self.pool[bounced_model].message_receive_bounce(cr, uid, [bounced_thread_id], mail_id=bounced_mail_id, context=context)
                return False

        return True

    def message_route(self, cr, uid, message, message_dict, model=None, thread_id=None,
                      custom_values=None, context=None):
        if not self.message_route_check_bounce(cr, uid, message, context=context):
            return []
        return super(MailThread, self).message_route(cr, uid, message, message_dict, model, thread_id, custom_values, context)

    def message_receive_bounce(self, cr, uid, ids, mail_id=None, context=None):
        """Called by ``message_process`` when a bounce email (such as Undelivered
        Mail Returned to Sender) is received for an existing thread. The default
        behavior is to check is an integer  ``message_bounce`` column exists.
        If it is the case, its content is incremented. """
        if self._all_columns.get('message_bounce'):
            for obj in self.browse(cr, uid, ids, context=context):
                self.write(cr, uid, [obj.id], {'message_bounce': obj.message_bounce + 1}, context=context)

    def message_route_process(self, cr, uid, msg, routes, context=None):
        if msg.get('message_id'):
            self.pool['mail.mail.statistics'].set_replied(cr, uid, mail_message_ids=[msg.get('message_id')], context=context)
        return super(MailThread, self).message_route_process(cr, uid, msg, routes, context=context)
