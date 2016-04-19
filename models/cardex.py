# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import fields,osv
import csv, os
import unicodedata
import base64
from datetime import datetime


class cardex_cardex(osv.osv_memory):
    _name = 'cardex.cardex'
    _columns = {
        'product_ids': fields.many2many('product.product', 'cardex_product_rel', 'cardex_id','product_id', 'Productos'),
        'location_id': fields.many2one('stock.location', 'Ubicacion de Stock'),
        'date': fields.date('Fecha'),        
        'csv_file' :fields.binary('Csv Report File', readonly=True),
        'export_filename': fields.char('Export CSV Filename', size=128)                
    }
    
    def report_cardex(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wz = self.browse(cr, uid, ids[-1], context)
        context['product_ids'] =  map(lambda x:x.id, wz.product_ids) 
        context['date'] = wz.date
        context['location_id'] = wz.location_id        
        data = self.__search_stock_move_by_products(cr, uid, ids, context)
        res = self.__create_csv(cr, uid, ids, data, context)
        return {
            'name': 'Reporte de inventario',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res and res[1] or False],
            'res_model': 'cardex.cardex',
            'context': "{}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'res_id': ids[0]  or False,##please replace record_id and provide the id of the record to be opened 
        }

    def special(self,valor):# saco caracteres especiales
        if valor == None:
            return ''
        return str(unicodedata.normalize('NFKD', unicode(valor)).encode('ascii','ignore'))


    def __create_csv(self, cr, uid, ids, data, context=None):
        path = '/tmp/reporte_inventario.csv'
        fieldnames = ['date', 'description','in','out','residue','pin','pout','presidue']
        pp = self.pool.get('product.product')
        with open(path, 'a') as myfile:            
            writer = csv.DictWriter(myfile, delimiter=';',fieldnames=fieldnames)            
            x = 0
            for cont in data:
                x+=1
                product = pp.browse(cr, uid, int(cont.keys()[0]))
                writer.writerow({
                 'description':'Codigo: %s' % product.default_code,
                 })
                writer.writerow({
                 'description':'Nombre: %s' % self.special(product.name),
                 })
                writer.writerow({
                 'out': 'Cantidad',
                 'pout': 'Precio Promedio Unitario',
                 })
                writer.writerow({
                 'date': 'Fecha',
                 'description':'Descripcion',
                 'in': 'Entrada',
                 'out': 'Salida',
                 'residue': 'Saldo',
                 'pin': 'Entrada',
                 'pout': 'Salida',
                 'presidue': 'Saldo'
                 })
        
                for d in cont[cont.keys()[0]]:                        
                    writer.writerow({
                                     'date': datetime.strptime(d['date'][:10],'%Y-%m-%d').strftime('%d-%m-%Y') if d['date'] else '',
                                     'description': self.special(d['description']),
                                     'in': d['in'],
                                     'out': d['out'],
                                     'residue': d['residue'],
                                     'pin': d['p_in'],
                                     'pout': d['p_out'],
                                     'presidue': d['p_residue']
                                 })
                else:
                    writer.writerow({
                                     'date': '',
                                     'description':'',
                                     'in': '',
                                     'out': '',
                                     'residue': '',
                                     'pin': '',
                                     'pout': '',
                                     'presidue': ''
                                     })
                    
        with open(path, 'r') as myfile:
            b64data = base64.b64encode(myfile.read())
        self.write(cr, uid, ids, {'csv_file':b64data}, {})
        self.write(cr, uid, ids, {'export_filename':'reporte_inventario.csv'}, {})
        os.remove(path)
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'econube_reporte_stock', 'report_cardex_cardex')        
        return res

    def validate_uom_product(self, cr, uid, ids, stock, context=None):
        if stock.origin:
            origin = stock.origin[:stock.origin.index(':')] if ':' in stock.origin else stock.origin 
        elif 'fv:inventario' in stock.name.lower():
            origin = '/'
        purchase_order = self.pool.get('purchase.order')
        line = []
        if origin and 'po' in origin.lower():
            id = purchase_order.search(cr, uid, [('name','=', origin)], limit=1)        
            for order in purchase_order.browse(cr, uid, id, context):
                line = filter( lambda x:x.product_id.id == stock.product_id.id , order.order_line)
            if line and line[0].product_uom.id != stock.product_id.uom_id.id:
                return round(line[0].product_qty / (1/line[0].product_uom.factor_inv)) , round(line[0].product_uom.factor_inv) 
        return stock.product_qty, False     
        
    def __search_stock_move_by_products(self, cr, uid, ids, context=None):
        stock_obj = self.pool.get('stock.move')
        data_print = []
        for product_id in context['product_ids']:
            if context['location_id']:
                st_ids = stock_obj.search(cr, uid, [('product_id','=', product_id),('state','=', 'done'),('date','<=', context['date']),('location_id','<=', context['location_id'].id)], order = 'date asc',context = context)
            else:
                st_ids = stock_obj.search(cr, uid, [('product_id','=', product_id),('state','=', 'done'),('date','<=', context['date'])], order = 'date asc',context = context)
            if not st_ids:
                continue
            data = {str(product_id): []}
            last_qty = 0
            last_residue = 0
            for stock in stock_obj.browse(cr, uid, st_ids, context):
                if stock.type == 'in':
                    d = {
                      'date' : stock.date, 
                      'description' : stock.origin,
                      'out' : 0,
                      'p_out' : 0
                    }
                    qty, factor = self.validate_uom_product(cr, uid, ids, stock, context)
                    d['in'] = qty 
                    price = self.__validate_residual(cr, uid, ids, stock, 'in', context)
                    self.validate_factor_price(factor, price, d)
                    d['residue'] = last_qty + d['in']
                    if not d['p_in'] or d['p_in'] == 0:
                        continue
                    last_residue = self.__validate_presidual(cr, uid, ids, last_qty, last_residue, d['p_in'],  d['in'], stock, 'in', context)
                    d['p_residue'] = last_residue 
                    last_qty += d['in']
                    data[str(product_id)].append(d)

                elif stock.type == 'out':
                    d = {
                      'date' : stock.date, 
                      'description' : stock.origin,
                      'in' : 0,
                      'out' : stock.product_qty,
                      'residue' : last_qty - stock.product_qty,
                      'p_in' : 0,
                      'p_out' : self.__validate_residual(cr, uid, ids, stock, 'out', context)
                    }
                    if not d['p_out']:
                        continue
                    last_residue = self.__validate_presidual(cr, uid, ids, last_qty, last_residue, d['p_out'], d['in'], stock, 'out', context)
                    d['p_residue'] = last_residue 
                    last_qty -= stock.product_qty
                    data[str(product_id)].append(d)

                elif 'fv:inventario' in stock.name.lower():
                    d = {
                      'date' : stock.date, 
                      'description' : stock.name,
                      'out' : 0,
                      'p_out' : 0
                    }
                    qty, factor = self.validate_uom_product(cr, uid, ids, stock, context)
                    d['in'] = qty 
                    price = self.__validate_residual(cr, uid, ids, stock, 'in', context)
                    self.validate_factor_price(factor, price, d)
                    d['residue'] = last_qty + d['in']
                    last_residue = self.__validate_presidual(cr, uid, ids, last_qty, last_residue, d['p_in'], d['in'], stock, 'in', context)
                    d['p_residue'] = last_residue 
                    last_qty += d['in']
                    data[str(product_id)].append(d)
            data_print.append(data)    
        return data_print
    
    def validate_factor_price(self, factor, price, d):
        if factor:
            d['p_in'] = price * (1/factor)
        else:
            d['p_in'] = price if price else 0

    
    def __validate_residual(self, cr, uid, ids, stock, type, context=None):
        
        if stock.origin:
            origin = stock.origin[:stock.origin.index(':')] if ':' in stock.origin else stock.origin 
        elif 'fv:inventario' in stock.name.lower():
            origin = '/'
        invoice = self.pool.get('account.invoice')
        if type == 'in':
            if 'fact' in origin.lower():
                id = invoice.search(cr, uid, [('number','=', origin)], limit=1)
                for inv in invoice.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id , inv.invoice_line)
                    return line[0].price_unit
                return 1

            elif 'po' in origin.lower():
                purchase_order = self.pool.get('purchase.order')
                id = purchase_order.search(cr, uid, [('name','=', origin)], limit=1)        
                for order in purchase_order.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id , order.order_line)
                    return line[0].price_unit
                return 1                

            elif 'trans' in origin.lower() or 'bol' in origin.lower():                 
                pos_order = self.pool.get('pos.order')
                id = pos_order.search(cr, uid, [('name','=', origin)], limit=1)
                for order in pos_order.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id , order.lines)
                    return line[0].price_unit
                return 1

            elif origin.lower() == '/' and stock.picking_id:
                account_move = self.pool.get('account.move')
                id = account_move.search(cr, uid, [('ref','=', stock.picking_id.name),('amount','>', 0)])        
                for order in account_move.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id and x.debit >0, order.line_id)
                    if line:
                        return line[0].debit / stock.product_qty
                return 1

        elif type == 'out':                
            if stock.name:
                cr.execute("""
                    select debit from account_move_line 
                    where name = '%s' 
                    and account_id = 2262
                    and debit >0
                    and product_id = %d
                    order by id desc limit 1
                """% (stock.name, stock.product_id.id))
                price = cr.fetchone()
                if price and price[0] is not None:
                    return price[0]
            
            if 'fact' in origin.lower():
                id = invoice.search(cr, uid, [('number','=', origin)], limit=1)
                for inv in invoice.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id , inv.invoice_line)
                    if line:
                        return line[0].price_unit

            elif 'trans' in origin.lower() or 'bol' in origin.lower():                 
                pos_order = self.pool.get('pos.order')
                id = pos_order.search(cr, uid, [('name','=', origin)], limit=1)
                for order in pos_order.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id , order.lines)
                    if line:
                        return line[0].price_unit
            elif 'nv' in origin.lower():
                sale_order = self.pool.get('sale.order')
                id = sale_order.search(cr, uid, [('name','=', origin)], limit=1)        
                for order in sale_order.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id , order.order_line)
                    if line:
                        return line[0].price_unit

            elif origin.lower() == '/' and stock.picking_id:
                account_move = self.pool.get('account.move')
                id = account_move.search(cr, uid, [('ref','=', stock.picking_id.name),('amount','>', 0)])        
                for order in account_move.browse(cr, uid, id, context):
                    line = filter( lambda x:x.product_id.id == stock.product_id.id and x.credit >0, order.line_id)
                    if line:
                        return line[0].credit / stock.product_qty
            return stock.product_id.list_price
        return False
        
    def __validate_presidual(self, cr, uid, ids, last_qty, last_residue, price, qty, stock, type, context):
        if type == 'in':
            if last_qty + qty != 0:
                return (qty * price + 
                         last_qty * last_residue
                        )/ (last_qty + qty)
            else:
                return (qty * price + 
                         last_qty * last_residue
                        )/ 1
                
        elif type == 'out':
            if last_qty - stock.product_qty != 0:
                return ( last_qty * last_residue)/ (last_qty - stock.product_qty)
            else:
                return ( last_qty * last_residue)/ 1
cardex_cardex()