
from osv import fields, osv
import time
import xmlrpclib
import pooler

oduser = "admin"
odpass = "o2aevl8w"

class odms_vserver(osv.osv):
	_name = "odms.vserver"
	_description = "ODMS Virtual Server"

	_columns = {
		'name': fields.char('Vserver ID', size=64, required=True),
		'ipaddress': fields.char('IP address', size=16, required=True),
		'state' : fields.selection([('notactive','Not active'),('active','Active')],'State', readonly=True),
	}
	_defaults = {
                'state': lambda *a: 'notactive',
	}
odms_vserver()

class odms_server(osv.osv):
	_name = "odms.server"
	_description = "ODMS Server Configuration"

	def srv_connect(self, cr, uid, ids, context={}):
		
		self.write(cr, uid, ids, {'state':'connected'})
		return True	

	def srv_disconnect(self, cr, uid, ids, context={}):
		
		self.write(cr, uid, ids, {'state':'notconnected'})
		return True	

	_columns = {
		'name': fields.char('Server name', size=64,required=True),
		'ipaddress': fields.char('IP address', size=16, required=True),
		'port': fields.char('Port', size=5, required=True),
		'user': fields.char('User', size=64, required=True),
		'password': fields.char('User password', size=64, required=True, invisible=True),
		'has_web': fields.boolean('Web service'), 
		'has_vserv': fields.boolean('Vserver service'), 
		'has_bckup': fields.boolean('Backup service'), 
		'nbr_vserv': fields.integer('Number of Virtual Servers', readonly=True),
		'notes': fields.text('Notes'),
		'state' : fields.selection([('notconnected','Not connected'),('connected','connected')],'State', readonly=True),
	}
	_defaults = {
                'has_web': lambda *a: False,
                'has_vserv': lambda *a: False,
                'has_bckup': lambda *a: False,
                'state': lambda *a: 'notconnected',
	}
odms_server()


class odms_bundle(osv.osv):
	_name = "odms.bundle"
	_description = "ODMS bundle"
	_columns = {
		'name': fields.char('Name', size=64, required=True),
		'product_id': fields.many2one('product.product','Product', required=True),
		'price_type': fields.selection([('fixed','Fixed'),('byusers','By users')],'Price type', required=True),
		'module_ids': fields.one2many('odms.module', 'bundle_id', 'Modules'),
	}
	_defaults = {
		'price_type': lambda *a: 'byusers',
	}
odms_bundle()


class odms_module(osv.osv):
        _name = "odms.module"
        _description = "ODMS Module"
        _columns = {
                'name': fields.char('Name', size=64, required=True),
                'bundle_id': fields.many2one('odms.bundle', 'Bundle', required=True),
		'state' : fields.selection([('installed','Installed'),('notinstalled','Not installed')],'State'),
        }
	_defaults = {
		'state': lambda *a: 'notinstalled',
	}
odms_module()


class odms_offer(osv.osv):
	_name = "odms.offer"
	_description = "ODMS Offer"
	_columns = {
		'name': fields.char('Name', size=64, required=True),
		'description': fields.char('Description', size=128),
		'bundle_ids': fields.many2many('odms.bundle', 'odms_offer_bundles_rel', 'offer', 'bundle', 'Bundles'),
		'active': fields.boolean('Active'),
	}
	_defaults = {
		'active': lambda *a: True,
	}
odms_offer()


class odms_partner(osv.osv):
        _name = "odms.partner"
        _description = "ODMS Partner"

	def create_partner(self, cr, uid, ids, context={}):
		odpart = self.browse(cr, uid , ids)[0]
			
		# Create new partner
		partner_obj = self.pool.get('res.partner')		
	
		part_id = partner_obj.create(cr, uid,
				{'name':odpart.name, 'vat':odpart.vat, 'website':odpart.website,
					'comment':odpart.notes})

		# Create new partner address
		# TODO : Add country and state
		paddr_obj = self.pool.get('res.partner.address')		
		paddr_id = paddr_obj.create(cr, uid,
				{'partner_id':part_id, 'name':odpart.contactname, 'street':odpart.address,
					 'zip':odpart.zip, 'city':odpart.city, 'email':odpart.email, 
						'phone': odpart.phone, 'type': 'contact'})

		# Add partner to subscription
		subs_obj = self.pool.get('odms.subscription')		
		subs_id = subs_obj.search(cr, uid, [('odpartner_id','=',odpart.id)])
		subs_obj.write(cr, uid, subs_id, {'partner_id':part_id})

		# Link partner
		self.write(cr, uid, ids, {'partner_id':part_id})

		# Change state
		self.write(cr, uid, ids, {'state':'created'})
		return True

        _columns = {
                'name': fields.char('Name', size=128, required=True),
		'partner_id': fields.many2one('res.partner', 'Partner'),
                'vat': fields.char('VAT', size=32),
                'contactname': fields.char('Contact name', size=64, required=True),
		'email': fields.char('Email', size=64, required=True),
                'address': fields.char('Address', size=128),
                'zip': fields.char('zip', size=24),
                'city': fields.char('city', size=128),
                'countrystate_id': fields.many2one('res.country.state','Country state'),
                'country_id': fields.many2one('res.country','country'),
                'phone': fields.char('phone', size=64),
		'website': fields.char('Website', size=64),
		'notes': fields.text('Notes'),
		'state': fields.selection([('draft','Draft'),('created','Created')],'State',readonly=True),
        }
	_defaults = {
                'state': lambda *a: 'draft',
	}
odms_partner()

class odms_subscription(osv.osv):
	_name = "odms.subscription"
	_description = "On Demand Subscription"


        def create(self, cr, uid, vals, context=None):
       		# Create subs bundles
		print "DEBUG vals :",vals

		# Create subscription
		res =  super(odms_subscription, self).create(cr, uid, vals,
                                context=context)

		if 'offer_id' in vals:
			print "DEBUG subs offer :",vals['offer_id']
			subs = self.browse(cr, uid, [res])[0]
			print "DEBUG subs id :",subs.id
			print "DEBUG subs offer bundles :",subs.offer_id.bundle_ids
	
			bundles = []
			offer_bdl_list = []
			bundle_obj = self.pool.get('odms.bundle')
			subs_bundle_obj = self.pool.get('odms.subs_bundle')

			# Get all bundles
			bids = bundle_obj.search(cr, uid, [('id','!=',False)])
			bundle_list = bundle_obj.browse(cr, uid, bids)
			print "DEBUG bundle list :",bundle_list
		
			# Create offer bundle list
			for bdl in subs.offer_id.bundle_ids:
				offer_bdl_list.append(bdl.id)
			print "DEBUG subs offer bundle list :",offer_bdl_list

			# Create subs bundles
			for bdl in bundle_list:
				# if bundle in offer set as installed 
				if bdl.id in offer_bdl_list:
					subs_bid = subs_bundle_obj.create(cr, uid,
						{'subscription_id':subs.id, 'bundle_id':bdl.id,'state':'installed'})
				else:
					subs_bid = subs_bundle_obj.create(cr, uid,
						{'subscription_id':subs.id, 'bundle_id':bdl.id,'state':'notinstalled'})
				bundles.append(subs_bid)

			# TODO : Add some result checking
			wres = self.write(cr, uid, subs.id, {'bundle_ids':[(6,0,bundles)]})

		return res		

        def create_subs(self, cr, uid, ids, context={}):

                s = xmlrpclib.Server('http://localhost:8000')
                print "DEBUG user : ",oduser
                print "DEBUG password : ",odpass

                o = self.browse(cr, uid, ids)
                offer = o[0].offer.id
                print "DEBUG offer : ",offer

                res = s.create_vs(oduser,odpass,offer)
                print "DEBUG res : ",res

                #if (res <= 10): 
                #       return False

                self.write(cr, uid, ids, {'state':'active'})

                return res

	def create_trial(self, cr, uid, vals, context=None):

		return True


        def suspend_subs(self, cr, uid, vals, context=None):

                return True

        def delete_subs(self, cr, uid, vals, context=None):

                return True

	def settodraft(self, cr, uid, vals, context=None):
		
		return True

	def startstop_vserv(self, cr, uid, vals, context=None):

		return True

        def create_vserv(self, cr, uid, vals, context=None):

                return True

        def create_web(self, cr, uid, vals, context=None):

                return True

        def create_bckup(self, cr, uid, vals, context=None):

                return True

        def create_partner(self, cr, uid, ids, context={}):
		print "DEBUG - accessing create_partner"
		# Get OD partner id
                subs = self.browse(cr, uid ,[ids])[0]
		print "DEBUG - subs browse",subs
                odpart_obj = self.pool.get('odms.partner')
		print "DEBUG - odpart_obj",odpart_obj
		print "DEBUG - subs id",subs.odpartner_id.id
		odpart = odpart_obj.browse(cr, uid, [subs.odpartner_id.id])[0]
		print "DEBUG - odpart :",odpart

		# Get OD pricelist id
		# plist_obj = self.pool.get('product.pricelist')
		# ...

                # Create new partner
                partner_obj = self.pool.get('res.partner')

                part_id = partner_obj.create(cr, uid,
                                {'name':odpart.name, 'vat':odpart.vat, 'website':odpart.website,
                                        'comment':odpart.notes})

                # Create new partner address
                # TODO : Add country and state
                paddr_obj = self.pool.get('res.partner.address')
                paddr_id = paddr_obj.create(cr, uid,
                                {'partner_id':part_id, 'name':odpart.contactname, 'street':odpart.address,
                                         'zip':odpart.zip, 'city':odpart.city, 'email':odpart.email,
                                                'phone': odpart.phone, 'type': 'contact'})

                # Add partner to subscription
                self.write(cr, uid, subs.id, {'partner_id':part_id})

                # Link partner
                self.write(cr, uid, ids, {'partner_id':part_id})

		# Set pricelist
		#self.write(cr, uid, ids, {'pricelist_id':plist_id})
		
                # Change state
                odpart_obj.write(cr, uid, subs.odpartner_id.id, {'state':'created'})

                return {'partner_id':part_id}


	def make_invoice(self, cr, uid, ids, context={}):
		"""Create a new invoice for a subscription"""
                # Get subscrition
                subs_obj = self.browse(cr, uid, ids)

		for subs in subs_obj:
	                print "DEBUG - subs :",subs
	                print "DEBUG - subs.partner_id :",subs.partner_id.id
			if not subs.partner_id:
				raise osv.except_osv('Error !',
                                                        'There is no partner defined for this subscription')
			if not subs.pricelist_id:
                                raise osv.except_osv('Error !',
                                                        'There is no pricelist defined for this subscription')

	                # Get invoice account and taxes
	                a = subs.partner_id.property_account_receivable.id
	                print "DEBUG - Account :", a
	
			# Get invoice lines
	                bundles = subs.bundle_ids
	                print "DEBUG - bundles :", bundles
	                print "DEBUG - bundles  nbr :", len(bundles)
	                lines = []
				
	                # Build an invoice line for each bundle
	                for b in bundles:
				if b.state == 'installed':
	                		# Get invoice line account
	 	               		al =  b.bundle_id.product_id.product_tmpl_id.property_account_income.id
	                		if not al: 
	                       			al = b.bundle_id.product_id.categ_id.property_account_income_categ.id
	                		if not al: 
	                        		raise osv.except_osv('Error !',
							 'There is no income account defined for this product: "%s" (id:%d)'% (b.bundle_id.product_id.name, b.bundle_id.product_id.id))
	                		print "DEBUG - Line Account :", al
	
	                                # Get quantity
	                                if b.bundle_id.price_type == 'fixed':
	                                        qty = 1
	                                else:
	                                        qty = subs.max_users
	                                print "DEBUG - qty :", qty
		
					# get price_unit
					pu = self.pool.get('product.pricelist').price_get(cr, uid, [subs.pricelist_id.id],
		                                b.bundle_id.product_id.id, qty or 1.0, subs.partner_id)[subs.pricelist_id.id]
	                                print "DEBUG - pu :",pu
	
					# get taxes
		                	taxes = b.bundle_id.product_id.taxes_id
	        	        	print "DEBUG - Taxes :", taxes
	                		for t in taxes:
	                        		print "DEBUG - Tax :", t.name
					# Create invoice lines	
	                        	inv_line_id = self.pool.get('account.invoice.line').create(cr, uid, {
	                        	        'name': b.bundle_id.name,
	                        	        'account_id': al,
	                        	        'price_unit': pu,
	                        	        'quantity': qty,
	                        	        'uos_id': 1,
	                        	        'product_id': b.bundle_id.product_id.id,
	                        	        'invoice_line_tax_id': [(6,0,[t.id for t in taxes])],
	                        	})
	                        	lines.append(inv_line_id)
	
	                # Get payment term
	                if subs.partner_id and subs.partner_id.property_payment_term.id:
	                        pay_term = subs.partner_id.property_payment_term.id
	                else:
	                        pay_term = False
	
	                # Get invoice address
	                invoice_add_id = subs.partner_id.address_get(cr, uid, [subs.partner_id.id], ['invoice'])
	                print "DEBUG - invoice_add_id :",  invoice_add_id
	
	                # Get contact address
	                contact_add_id = subs.partner_id.address_get(cr, uid, [subs.partner_id.id], ['contact'])
	                print "DEBUG - contact_add_id :",  contact_add_id
	
			# Get user => get company => get currency
	                user = self.pool.get('res.users').browse(cr, uid, [uid])
	                print "DEBUG - user :", user[0]
	                print "DEBUG - company :", user[0].company_id.id
	                company = user[0].company_id
	                currency = company.currency_id
	                print "DEBUG - currency :",  currency.id
	
	                # Set invoice
	                inv = {
	                        'name': subs.name,
	                        'origin': subs.name,
	                        'type': 'out_invoice',
	                        'reference': "P%dSO%d"%(subs.partner_id.id,subs.id),
	                        'account_id': a,
	                        'partner_id': subs.partner_id.id,
	                        'address_invoice_id': invoice_add_id['invoice'],
	                        'address_contact_id': contact_add_id['contact'],
	                        'invoice_line': [(6,0,lines)],
	                        'currency_id' : currency.id,
	                        'comment': subs.notes,
	                        'payment_term': pay_term,
	                }
	                # Create invoice
	                inv_obj = self.pool.get('account.invoice')
	                inv_id = inv_obj.create(cr, uid, inv)
	                inv_obj.button_compute(cr, uid, [inv_id])
	
                print "DEBUG - inv_id :", inv_id
                return inv_id


	def onchange_partner_id(self, cr, uid, ids, part):
                if not part:
                        return {'value':{'pricelist':False}}                
                pricelist = self.pool.get('res.partner').browse(cr, uid, part).property_product_pricelist.id
                return {'value':{'pricelist_id': pricelist}}
	
	
	_columns = {
		'name' : fields.char('Subscription name', size=64, required=True),
		'partner_id': fields.many2one('res.partner', 'Partner'),
		'odpartner_id': fields.many2one('odms.partner', 'ODMS Partner'),
		'email': fields.char('Login', size=64, required=True),
		'password': fields.char('Password', size=64, required=True),
		'date' : fields.date('Subscription date', readonly=True),
		'activ_date' : fields.date('Activation date'),
		'deadline_date' : fields.date('Deadline date'),
		'nbr_users' : fields.integer('Number of users',readonly=True),
		'max_users' : fields.integer('Maximum users'),
		'offer_id' : fields.many2one('odms.offer', 'Offer', required=True),
		'pricelist_id':fields.many2one('product.pricelist', 'Pricelist', readonly=True, states={'draft':[('readonly',False)]}),
		'bundle_ids' : fields.one2many('odms.subs_bundle', 'subscription_id', 'Bundles'),
		'vserver_id': fields.many2one('odms.vserver', 'VServer ID', readonly=True),
		'vserver_state': fields.selection([('noactive','Not active'),('active','Active')], 'VServer status', readonly=True),
		'web_server_id': fields.many2one('odms.server', 'ODMS Web Server'),
		'web_server_state' : fields.selection([('notinstalled','Not installed'),('installing','Installing'),('installed','Installed')],'Web server state', readonly=True),
		'vserv_server_id': fields.many2one('odms.server', 'ODMS VServer Server'),
		'vserv_server_state' : fields.selection([('notinstalled','Not installed'),('installing','Installing'),('installed','Installed')],'VServer server state', readonly=True),
		'bckup_server_id': fields.many2one('odms.server', 'ODMS Backup Server'),
		'bckup_server_state' : fields.selection([('notinstalled','Not installed'),('installing','Installing'),('installed','Installed')],'Backup server state', readonly=True),
		'notes' : fields.text('Notes'),
		'state' : fields.selection([('draft','Draft'),('trial','Free trial'),('active','Active'),('suspended','Suspended'),('deleted','Deleted')],'State', readonly=True),
	}

	_defaults = {
		'date' : lambda *a: time.strftime('%Y-%m-%d'),
		'state' : lambda *a: 'draft',
		'web_server_state' : lambda *a: 'notinstalled',
		'vserv_server_state' : lambda *a: 'notinstalled',
		'bckup_server_state' : lambda *a: 'notinstalled',
	}
	_order = "date desc"
odms_subscription()


class odms_subs_bundle(osv.osv):
        _name = "odms.subs_bundle"
        _description = "ODMS Subscription bundle"

	def install_bundle(self, cr, uid, ids, context={}):
		# ...
		self.write(cr, uid, ids, {'state':'installed'})
		return True

	def uninstall_bundle(self, cr, uid, ids, context={}):
		# ...
		self.write(cr, uid, ids, {'state':'notinstalled'})
		return True

	_columns = {
                'subscription_id': fields.many2one('odms.subscription', 'Subscription', required=True),
                'bundle_id': fields.many2one('odms.bundle', 'Bundle', required=True),
		'state' : fields.selection([('installed','Installed'),('notinstalled','Not installed')],'State', readonly=True),
        }
        _defaults = {
               'state': lambda *a: 'notinstalled',
        }
	_rec_name = 'bundle_id'
odms_subs_bundle()

