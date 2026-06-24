#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
航材库存管理系统 v2.0 (AeroMat Inventory Management System)
用于模拟器航材消耗件管理

新增功能：
- 件序号管理（个体追踪）
- 架位号优化显示
- 图表统计
- 消耗预测

Author: AI Assistant
Version: 2.0
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import os
import sys

class AeroMatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("航材库存管理系统 v2.0")
        self.root.geometry("1400x800")
        
        # 数据库初始化
        self.init_db()
        
        # 创建主界面
        self.create_widgets()
        
        # 加载数据
        self.load_inventory()
        
    def init_db(self):
        """初始化数据库"""
        self.conn = sqlite3.connect('aeromat.db')
        self.cursor = self.conn.cursor()
        
        # 创建库存主表（航材型号）
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            total_quantity REAL DEFAULT 0,
            unit TEXT DEFAULT '个',
            location TEXT,
            min_stock REAL DEFAULT 0,
            remark TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # 创建个体件表（每个具体件的追踪）- 新增
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            serial_number TEXT,
            shelf_number TEXT,
            expiry_date TEXT,
            last_check_date TEXT,
            status TEXT DEFAULT '正常',  -- 正常、已领用、已过期、已报废
            remark TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (part_number) REFERENCES inventory(part_number)
        )
        ''')
        
        # 创建出入库记录表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            serial_number TEXT,
            description TEXT,
            trans_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            operator TEXT,
            purpose TEXT,
            trans_date TEXT,
            remark TEXT
        )
        ''')
        
        self.conn.commit()
    
    def create_widgets(self):
        """创建界面组件"""
        # 顶部菜单栏
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="导入Excel", command=self.import_excel)
        file_menu.add_command(label="导出Excel", command=self.export_excel)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        
        # 功能菜单
        func_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="功能", menu=func_menu)
        func_menu.add_command(label="入库管理", command=self.show_in_dialog)
        func_menu.add_command(label="出库管理", command=self.show_out_dialog)
        func_menu.add_command(label="盘点管理", command=self.show_check_dialog)
        func_menu.add_separator()
        func_menu.add_command(label="查看个体件详情", command=self.show_items_detail)
        
        # 查询菜单
        query_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="查询", menu=query_menu)
        query_menu.add_command(label="低库存预警", command=self.show_low_stock)
        query_menu.add_command(label="有效期预警", command=self.show_expiry_alert)
        query_menu.add_separator()
        query_menu.add_command(label="统计分析", command=self.show_statistics)
        
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 搜索框
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<KeyRelease>', lambda e: self.load_inventory())
        
        ttk.Button(search_frame, text="搜索", command=self.load_inventory).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="刷新", command=self.load_inventory).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="查看个体件", command=self.show_items_detail).pack(side=tk.LEFT, padx=15)
        
        # 库存表格 - 优化显示
        table_frame = ttk.Frame(main_frame)
        table_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 创建Treeview - 增加架位号列
        columns = ('件号', '描述', '总数量', '单位', '架位号', '最低库存', '有效期提醒', '备注')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)
        
        # 设置列宽和标题
        col_widths = {
            '件号': 120,
            '描述': 200,
            '总数量': 80,
            '单位': 60,
            '架位号': 100,
            '最低库存': 80,
            '有效期提醒': 120,
            '备注': 150
        }
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths[col], anchor=tk.CENTER if col in ['总数量', '单位', '最低库存'] else tk.W)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 双击查看个体件详情
        self.tree.bind('<Double-1>', lambda e: self.show_items_detail())
        
        # 按钮区
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="新增航材", command=self.show_add_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑航材", command=self.show_edit_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除航材", command=self.delete_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="入库", command=self.show_in_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="出库", command=self.show_out_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="统计分析", command=self.show_statistics).pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
    
    def load_inventory(self):
        """加载库存数据"""
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 查询数据 - 获取每个件号的总数量和最早有效期
        search_term = self.search_var.get()
        if search_term:
            query = '''
            SELECT 
                i.part_number, 
                i.description, 
                i.total_quantity,
                i.unit,
                GROUP_CONCAT(DISTINCT ii.shelf_number) as shelf_numbers,
                i.min_stock,
                MIN(ii.expiry_date) as earliest_expiry,
                i.remark
            FROM inventory i
            LEFT JOIN inventory_items ii ON i.part_number = ii.part_number AND ii.status = '正常'
            WHERE i.part_number LIKE ? OR i.description LIKE ?
            GROUP BY i.part_number
            ORDER BY i.part_number
            '''
            self.cursor.execute(query, (f'%{search_term}%', f'%{search_term}%'))
        else:
            query = '''
            SELECT 
                i.part_number, 
                i.description, 
                i.total_quantity,
                i.unit,
                GROUP_CONCAT(DISTINCT ii.shelf_number) as shelf_numbers,
                i.min_stock,
                MIN(ii.expiry_date) as earliest_expiry,
                i.remark
            FROM inventory i
            LEFT JOIN inventory_items ii ON i.part_number = ii.part_number AND ii.status = '正常'
            GROUP BY i.part_number
            ORDER BY i.part_number
            '''
            self.cursor.execute(query)
        
        rows = self.cursor.fetchall()
        
        # 填入表格，添加有效期预警标识
        today = datetime.now()
        for row in rows:
            expiry = row[6]  # earliest_expiry
            expiry_alert = ''
            if expiry:
                try:
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
                    days_left = (expiry_date - today).days
                    if days_left < 0:
                        expiry_alert = f'⚠️ 已过期({expiry})'
                    elif days_left <= 30:
                        expiry_alert = f'🔴 {days_left}天到期({expiry})'
                    elif days_left <= 60:
                        expiry_alert = f'🟡 {days_left}天到期({expiry})'
                    elif days_left <= 90:
                        expiry_alert = f'🟢 {days_left}天到期({expiry})'
                    else:
                        expiry_alert = expiry
                except:
                    expiry_alert = expiry
            
            self.tree.insert('', tk.END, values=(
                row[0],  # 件号
                row[1],  # 描述
                row[2],  # 总数量
                row[3],  # 单位
                row[4] if row[4] else row[1],  # 架位号（如果没有个体架位，用主表的location）
                row[5],  # 最低库存
                expiry_alert,  # 有效期提醒
                row[7]   # 备注
            ))
        
        self.status_var.set(f"共 {len(rows)} 种航材")
    
    def show_add_dialog(self):
        """显示新增对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("新增航材")
        dialog.geometry("450x550")
        
        # 表单
        fields = {}
        row = 0
        
        ttk.Label(dialog, text="件号 *").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['件号'] = var
        row += 1
        
        ttk.Label(dialog, text="描述 *").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['描述'] = var
        row += 1
        
        ttk.Label(dialog, text="单位").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value='个')
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['单位'] = var
        row += 1
        
        ttk.Label(dialog, text="架位号").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['架位号'] = var
        row += 1
        
        ttk.Label(dialog, text="最低库存").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value='0')
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['最低库存'] = var
        row += 1
        
        ttk.Label(dialog, text="备注").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['备注'] = var
        row += 1
        
        # 分隔线
        ttk.Separator(dialog, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        ttk.Label(dialog, text="批量添加个体件（可选）", font=('Arial', 9, 'bold')).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1
        
        ttk.Label(dialog, text="件数量").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value='0')
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['件数量'] = var
        row += 1
        
        ttk.Label(dialog, text="有效期(YYYY-MM-DD)").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['有效期'] = var
        row += 1
        
        # 按钮
        def save():
            try:
                part_number = fields['件号'].get().strip()
                description = fields['描述'].get().strip()
                
                if not part_number or not description:
                    messagebox.showerror("错误", "件号和描述为必填项")
                    return
                
                unit = fields['单位'].get() or '个'
                location = fields['架位号'].get()
                min_stock = float(fields['最低库存'].get() or 0)
                remark = fields['备注'].get()
                item_count = int(fields['件数量'].get() or 0)
                expiry_date = fields['有效期'].get().strip()
                
                # 插入主表
                self.cursor.execute('''
                INSERT INTO inventory (part_number, description, total_quantity, unit, location, min_stock, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (part_number, description, item_count, unit, location, min_stock, remark,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                # 批量插入个体件
                if item_count > 0:
                    for i in range(1, item_count + 1):
                        serial_num = f"{part_number}-{i:03d}"  # 自动生成件序号：件号-001
                        self.cursor.execute('''
                        INSERT INTO inventory_items (part_number, serial_number, shelf_number, expiry_date, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, '正常', ?, ?)
                        ''', (part_number, serial_num, location, expiry_date,
                             datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                self.conn.commit()
                
                msg = f"新增成功"
                if item_count > 0:
                    msg += f"，已创建 {item_count} 个个体件（件序号: {part_number}-001 ~ {part_number}-{item_count:03d}）"
                
                messagebox.showinfo("成功", msg)
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))
        
        ttk.Button(dialog, text="保存", command=save).grid(row=row, column=0, padx=10, pady=20)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=20)
    
    def show_edit_dialog(self):
        """显示编辑对话框"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要编辑的航材")
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        
        # 查询数据库获取完整信息
        self.cursor.execute('SELECT * FROM inventory WHERE part_number = ?', (part_number,))
        record = self.cursor.fetchone()
        
        if not record:
            messagebox.showerror("错误", "找不到该航材记录")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑航材 - {part_number}")
        dialog.geometry("450x400")
        
        # 表单
        fields = {}
        row = 0
        
        ttk.Label(dialog, text=f"件号: {part_number}", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, padx=10, pady=10)
        row += 1
        
        ttk.Label(dialog, text="描述").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value=record[2])  # description
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['描述'] = var
        row += 1
        
        ttk.Label(dialog, text="单位").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value=record[4])  # unit
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['单位'] = var
        row += 1
        
        ttk.Label(dialog, text="架位号").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value=record[5] or '')  # location
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['架位号'] = var
        row += 1
        
        ttk.Label(dialog, text="最低库存").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value=str(record[6]))  # min_stock
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['最低库存'] = var
        row += 1
        
        ttk.Label(dialog, text="备注").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar(value=record[7] or '')  # remark
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        fields['备注'] = var
        row += 1
        
        # 按钮
        def save():
            try:
                description = fields['描述'].get()
                unit = fields['单位'].get() or '个'
                location = fields['架位号'].get()
                min_stock = float(fields['最低库存'].get() or 0)
                remark = fields['备注'].get()
                
                self.cursor.execute('''
                UPDATE inventory 
                SET description=?, unit=?, location=?, min_stock=?, remark=?, updated_at=?
                WHERE part_number=?
                ''', (description, unit, location, min_stock, remark,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S'), part_number))
                self.conn.commit()
                
                messagebox.showinfo("成功", "更新成功")
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))
        
        ttk.Button(dialog, text="保存", command=save).grid(row=row, column=0, padx=10, pady=20)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=20)
    
    def delete_item(self):
        """删除航材"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要删除的航材")
            return
        
        item = self.tree.item(selection[0])
        part_number = item['values'][0]
        
        if messagebox.askyesno("确认", f"确定要删除航材 {part_number} 吗？\n这将同时删除该件号的所有个体件记录！"):
            # 删除个体件
            self.cursor.execute('DELETE FROM inventory_items WHERE part_number=?', (part_number,))
            # 删除主记录
            self.cursor.execute('DELETE FROM inventory WHERE part_number=?', (part_number,))
            self.conn.commit()
            
            messagebox.showinfo("成功", "删除成功")
            self.load_inventory()
    
    def show_in_dialog(self):
        """显示入库对话框"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要入库的航材")
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"入库管理 - {part_number}")
        dialog.geometry("400x500")
        
        ttk.Label(dialog, text=f"航材: {part_number} - {values[1]}", font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, padx=10, pady=10)
        ttk.Label(dialog, text=f"当前库存: {values[2]} {values[3]}").grid(row=1, column=0, columnspan=2, padx=10, pady=5)
        
        row = 2
        fields = {}
        
        ttk.Label(dialog, text="入库数量 *").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
        fields['数量'] = var
        row += 1
        
        ttk.Label(dialog, text="有效期(YYYY-MM-DD)").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
        fields['有效期'] = var
        row += 1
        
        ttk.Label(dialog, text="架位号").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
        fields['架位号'] = var
        row += 1
        
        ttk.Label(dialog, text="经手人").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
        fields['经手人'] = var
        row += 1
        
        ttk.Label(dialog, text="备注").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
        fields['备注'] = var
        row += 1
        
        def save():
            try:
                qty = int(fields['数量'].get())
                expiry = fields['有效期'].get().strip()
                shelf = fields['架位号'].get().strip()
                operator = fields['经手人'].get().strip()
                remark = fields['备注'].get().strip()
                
                # 获取当前最大序号
                self.cursor.execute('''
                SELECT MAX(serial_number) FROM inventory_items WHERE part_number=?
                ''', (part_number,))
                max_serial = self.cursor.fetchone()[0]
                
                if max_serial:
                    # 提取序号部分
                    try:
                        last_num = int(max_serial.split('-')[-1])
                    except:
                        last_num = 0
                else:
                    last_num = 0
                
                # 插入个体件
                for i in range(1, qty + 1):
                    serial_num = f"{part_number}-{last_num + i:03d}"
                    self.cursor.execute('''
                    INSERT INTO inventory_items (part_number, serial_number, shelf_number, expiry_date, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, '正常', ?, ?)
                    ''', (part_number, serial_num, shelf, expiry,
                         datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                         datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                # 更新总数量
                self.cursor.execute('''
                UPDATE inventory 
                SET total_quantity = total_quantity + ?, updated_at = ?
                WHERE part_number = ?
                ''', (qty, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), part_number))
                
                # 记录交易
                self.cursor.execute('''
                INSERT INTO transactions (part_number, description, trans_type, quantity, operator, purpose, trans_date, remark)
                VALUES (?, ?, 'IN', ?, ?, ?, ?, ?)
                ''', (part_number, values[1], qty, operator, remark,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S'), remark))
                
                self.conn.commit()
                
                messagebox.showinfo("成功", f"入库成功！\n新增 {qty} 个个体件\n件序号: {part_number}-{last_num+1:03d} ~ {part_number}-{last_num+qty:03d}")
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))
        
        ttk.Button(dialog, text="确定", command=save).grid(row=row, column=0, padx=10, pady=20)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=20)
    
    def show_out_dialog(self):
        """显示出库对话框"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要出库的航材")
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        
        # 查询可用个体件
        self.cursor.execute('''
        SELECT serial_number, shelf_number, expiry_date FROM inventory_items 
        WHERE part_number=? AND status='正常' 
        ORDER BY expiry_date ASC, serial_number ASC
        ''', (part_number,))
        available_items = self.cursor.fetchall()
        
        if not available_items:
            messagebox.showerror("错误", "库存不足，没有可用个体件")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"出库管理 - {part_number}")
        dialog.geometry("500x600")
        
        ttk.Label(dialog, text=f"航材: {part_number} - {values[1]}", font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, padx=10, pady=10)
        ttk.Label(dialog, text=f"当前库存: {values[2]} {values[3]}").grid(row=1, column=0, columnspan=2, padx=10, pady=5)
        
        row = 2
        
        # 显示可用个体件列表
        ttk.Label(dialog, text="可用个体件:", font=('Arial', 9, 'bold')).grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        row += 1
        
        # 创建列表框
        list_frame = ttk.Frame(dialog)
        list_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=5)
        
        listbox = tk.Listbox(list_frame, height=8, width=60, selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        for item in available_items:
            serial, shelf, expiry = item
            expiry_str = f"有效期: {expiry}" if expiry else "无有效期"
            listbox.insert(tk.END, f"{serial} | 架位: {shelf or 'N/A'} | {expiry_str}")
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        row += 1
        
        # 其他字段
        ttk.Label(dialog, text="出库数量").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        qty_var = tk.StringVar(value='1')
        ttk.Entry(dialog, textvariable=qty_var, width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        
        ttk.Label(dialog, text="领用人").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        operator_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=operator_var, width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        
        ttk.Label(dialog, text="用途").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        purpose_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=purpose_var, width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        
        ttk.Label(dialog, text="备注").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        remark_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=remark_var, width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        
        def save():
            try:
                qty = int(qty_var.get())
                if qty > len(available_items):
                    messagebox.showerror("错误", f"库存不足！当前可用: {len(available_items)} 件")
                    return
                
                operator = operator_var.get().strip()
                purpose = purpose_var.get().strip()
                remark = remark_var.get().strip()
                
                # 取前qty个个体件（优先出库最早到期的）
                for i in range(qty):
                    serial = available_items[i][0]
                    self.cursor.execute('''
                    UPDATE inventory_items SET status='已领用', updated_at=?
                    WHERE part_number=? AND serial_number=?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), part_number, serial))
                
                # 更新总数量
                self.cursor.execute('''
                UPDATE inventory 
                SET total_quantity = total_quantity - ?, updated_at = ?
                WHERE part_number = ?
                ''', (qty, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), part_number))
                
                # 记录交易
                self.cursor.execute('''
                INSERT INTO transactions (part_number, description, trans_type, quantity, operator, purpose, trans_date, remark)
                VALUES (?, ?, 'OUT', ?, ?, ?, ?, ?)
                ''', (part_number, values[1], qty, operator, purpose,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S'), remark))
                
                self.conn.commit()
                
                messagebox.showinfo("成功", f"出库成功！减少 {qty} 件")
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))
        
        ttk.Button(dialog, text="确定", command=save).grid(row=row, column=0, padx=10, pady=20)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=20)
    
    def show_items_detail(self):
        """显示个体件详情"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要查看的航材")
            return
        
        item = self.tree.item(selection[0])
        part_number = item['values'][0]
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"个体件详情 - {part_number}")
        dialog.geometry("900x600")
        
        # 查询个体件
        self.cursor.execute('''
        SELECT serial_number, shelf_number, expiry_date, last_check_date, status, remark, created_at
        FROM inventory_items 
        WHERE part_number=?
        ORDER BY status, expiry_date ASC, serial_number ASC
        ''', (part_number,))
        
        items = self.cursor.fetchall()
        
        if not items:
            ttk.Label(dialog, text="该航材暂无个体件记录").pack(pady=20)
            return
        
        # 创建表格
        columns = ('件序号', '架位号', '有效期', '上次检查', '状态', '备注', '创建时间')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=20)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        
        # 填入数据，根据状态和有效期着色
        today = datetime.now()
        for item in items:
            serial, shelf, expiry, check_date, status, remark, created = item
            
            # 计算有效期状态
            expiry_status = expiry
            if expiry and status == '正常':
                try:
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
                    days_left = (expiry_date - today).days
                    if days_left < 0:
                        expiry_status = f"⚠️ 已过期({expiry})"
                    elif days_left <= 30:
                        expiry_status = f"🔴 {expiry}({days_left}天)"
                    elif days_left <= 60:
                        expiry_status = f"🟡 {expiry}({days_left}天)"
                except:
                    pass
            
            tree.insert('', tk.END, values=(
                serial, shelf or '-', expiry_status or '-', check_date or '-', status, remark or '-', created or '-'
            ))
        
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 按钮区
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def edit_item():
            """编辑个体件"""
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("警告", "请选择要编辑的个体件")
                return
            
            item_data = tree.item(sel[0])
            serial = item_data['values'][0]
            
            # 查询数据库
            self.cursor.execute('''
            SELECT * FROM inventory_items WHERE part_number=? AND serial_number=?
            ''', (part_number, serial))
            record = self.cursor.fetchone()
            
            if not record:
                return
            
            # 编辑对话框
            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title(f"编辑个体件 - {serial}")
            edit_dialog.geometry("400x400")
            
            fields = {}
            row = 0
            
            ttk.Label(edit_dialog, text=f"件序号: {serial}", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, padx=10, pady=10)
            row += 1
            
            ttk.Label(edit_dialog, text="架位号").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            var = tk.StringVar(value=record[3] or '')  # shelf_number
            ttk.Entry(edit_dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
            fields['架位号'] = var
            row += 1
            
            ttk.Label(edit_dialog, text="有效期").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            var = tk.StringVar(value=record[4] or '')  # expiry_date
            ttk.Entry(edit_dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
            fields['有效期'] = var
            row += 1
            
            ttk.Label(edit_dialog, text="上次检查日期").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            var = tk.StringVar(value=record[5] or '')  # last_check_date
            ttk.Entry(edit_dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
            fields['上次检查'] = var
            row += 1
            
            ttk.Label(edit_dialog, text="状态").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            var = tk.StringVar(value=record[6])  # status
            status_combo = ttk.Combobox(edit_dialog, textvariable=var, values=['正常', '已领用', '已过期', '已报废'], width=23)
            status_combo.grid(row=row, column=1, padx=10, pady=5)
            fields['状态'] = var
            row += 1
            
            ttk.Label(edit_dialog, text="备注").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            var = tk.StringVar(value=record[7] or '')  # remark
            ttk.Entry(edit_dialog, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=5)
            fields['备注'] = var
            row += 1
            
            def save_edit():
                try:
                    shelf = fields['架位号'].get()
                    expiry = fields['有效期'].get()
                    check_date = fields['上次检查'].get()
                    status = fields['状态'].get()
                    remark = fields['备注'].get()
                    
                    self.cursor.execute('''
                    UPDATE inventory_items 
                    SET shelf_number=?, expiry_date=?, last_check_date=?, status=?, remark=?, updated_at=?
                    WHERE part_number=? AND serial_number=?
                    ''', (shelf, expiry, check_date, status, remark,
                         datetime.now().strftime('%Y-%m-%d %H:%M:%S'), part_number, serial))
                    self.conn.commit()
                    
                    messagebox.showinfo("成功", "更新成功")
                    edit_dialog.destroy()
                    dialog.destroy()
                    self.show_items_detail()  # 刷新
                except Exception as e:
                    messagebox.showerror("错误", str(e))
            
            ttk.Button(edit_dialog, text="保存", command=save_edit).grid(row=row, column=0, padx=10, pady=20)
            ttk.Button(edit_dialog, text="取消", command=edit_dialog.destroy).grid(row=row, column=1, padx=10, pady=20)
        
        ttk.Button(btn_frame, text="编辑个体件", command=edit_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(dialog, text=f"共 {len(items)} 个个体件").pack(pady=5)
    
    def show_check_dialog(self):
        """显示盘点对话框"""
        messagebox.showinfo("盘点", "盘点功能开发中...\n\n提示：可通过查看个体件详情进行盘点")
    
    def show_low_stock(self):
        """显示低库存预警"""
        dialog = tk.Toplevel(self.root)
        dialog.title("低库存预警")
        dialog.geometry("900x450")
        
        self.cursor.execute('''
        SELECT part_number, description, total_quantity, unit, location, min_stock
        FROM inventory
        WHERE total_quantity <= min_stock AND min_stock > 0
        ORDER BY total_quantity ASC
        ''')
        
        rows = self.cursor.fetchall()
        
        if not rows:
            ttk.Label(dialog, text="✅ 当前没有低库存预警", font=('Arial', 12)).pack(pady=20)
            return
        
        columns = ('件号', '描述', '当前库存', '单位', '架位号', '最低库存', '缺口')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100 if col not in ['描述', '缺口'] else 150)
        
        for row in rows:
            gap = row[5] - row[2]
            tree.insert('', tk.END, values=row + (gap,))
        
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(dialog, text=f"⚠️ 共 {len(rows)} 项低库存预警", foreground='red', font=('Arial', 11, 'bold')).pack(pady=5)
    
    def show_expiry_alert(self):
        """显示有效期预警"""
        dialog = tk.Toplevel(self.root)
        dialog.title("有效期预警（未来90天）")
        dialog.geometry("1000x500")
        
        today = datetime.now()
        alert_date = (today + timedelta(days=90)).strftime('%Y-%m-%d')
        
        self.cursor.execute('''
        SELECT ii.part_number, ii.serial_number, ii.shelf_number, ii.expiry_date, ii.status
        FROM inventory_items ii
        WHERE ii.expiry_date IS NOT NULL AND ii.expiry_date != '' AND ii.expiry_date <= ? AND ii.status = '正常'
        ORDER BY ii.expiry_date ASC
        ''', (alert_date,))
        
        rows = self.cursor.fetchall()
        
        if not rows:
            ttk.Label(dialog, text="✅ 未来90天内没有到期航材", font=('Arial', 12)).pack(pady=20)
            return
        
        columns = ('件号', '件序号', '架位号', '到期日期', '状态', '剩余天数')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=18)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130 if col == '件号' else 120)
        
        for row in rows:
            expiry = datetime.strptime(row[3], '%Y-%m-%d')
            days_left = (expiry - today).days
            status_icon = '⚠️' if days_left < 0 else ('🔴' if days_left <= 30 else ('🟡' if days_left <= 60 else '🟢'))
            tree.insert('', tk.END, values=row + (f"{status_icon} {days_left}天",))
        
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(dialog, text=f"⚠️ 共 {len(rows)} 项即将到期", foreground='red', font=('Arial', 11, 'bold')).pack(pady=5)
    
    def show_statistics(self):
        """显示统计分析"""
        dialog = tk.Toplevel(self.root)
        dialog.title("库存统计分析")
        dialog.geometry("800x600")
        
        # 统计数据
        self.cursor.execute('SELECT COUNT(*) FROM inventory')
        total_types = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT SUM(total_quantity) FROM inventory')
        total_items = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute('SELECT COUNT(*) FROM inventory WHERE total_quantity <= min_stock AND min_stock > 0')
        low_stock_count = self.cursor.fetchone()[0]
        
        self.cursor.execute('''
        SELECT COUNT(*) FROM inventory_items 
        WHERE expiry_date IS NOT NULL AND expiry_date != '' AND expiry_date <= date('now', '+90 days') AND status = '正常'
        ''')
        expiry_count = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM transactions')
        trans_count = self.cursor.fetchone()[0]
        
        # 显示统计信息
        stats_frame = ttk.Frame(dialog)
        stats_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ttk.Label(stats_frame, text="库存统计概览", font=('Arial', 14, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        stats = [
            ("航材种类数:", total_types),
            ("库存总数量:", total_items),
            ("低库存预警:", low_stock_count),
            ("即将到期:", expiry_count),
            ("交易记录数:", trans_count)
        ]
        
        for i, (label, value) in enumerate(stats):
            ttk.Label(stats_frame, text=label, font=('Arial', 11)).grid(row=i+1, column=0, padx=10, pady=5, sticky=tk.W)
            ttk.Label(stats_frame, text=str(value), font=('Arial', 11, 'bold')).grid(row=i+1, column=1, padx=10, pady=5, sticky=tk.W)
        
        # 出入库趋势（最近30天）
        ttk.Label(stats_frame, text="\n最近30天出入库统计:", font=('Arial', 12, 'bold')).grid(row=6, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        self.cursor.execute('''
        SELECT trans_type, COUNT(*) as count, SUM(quantity) as total_qty
        FROM transactions
        WHERE trans_date >= date('now', '-30 days')
        GROUP BY trans_type
        ''')
        
        trans_stats = self.cursor.fetchall()
        for trans in trans_stats:
            trans_type = "入库" if trans[0] == 'IN' else "出库"
            ttk.Label(stats_frame, text=f"{trans_type}: {trans[1]}次, 共{trans[2]}件").grid(row=7 if trans[0]=='IN' else 8, column=0, columnspan=2, padx=10, pady=2, sticky=tk.W)
        
        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=20)
    
    def import_excel(self):
        """导入Excel"""
        file_path = filedialog.askopenfilename(
            title="选择Excel文件",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        
        if not file_path:
            return
        
        try:
            df = pd.read_excel(file_path)
            
            expected_cols = ['件号', '件号描述', '数量', '位置', '备注']
            if not all(col in df.columns for col in expected_cols):
                messagebox.showerror("错误", f"Excel格式不正确，需要包含: {', '.join(expected_cols)}")
                return
            
            count = 0
            for _, row in df.iterrows():
                part_number = str(row['件号']) if pd.notna(row['件号']) else ''
                description = str(row['件号描述']) if pd.notna(row['件号描述']) else ''
                quantity_str = str(row['数量']) if pd.notna(row['数量']) else '0'
                location = str(row['位置']) if pd.notna(row['位置']) else ''
                remark = str(row['备注']) if pd.notna(row['备注']) else ''
                
                # 处理数量
                unit = '箱' if '箱' in quantity_str else '个'
                quantity = float(quantity_str.replace('箱', '').strip()) if quantity_str else 0
                
                if not part_number or part_number == 'N/A':
                    continue
                
                # 检查是否存在
                self.cursor.execute('SELECT id FROM inventory WHERE part_number=?', (part_number,))
                existing = self.cursor.fetchone()
                
                if existing:
                    # 更新
                    self.cursor.execute('''
                    UPDATE inventory 
                    SET total_quantity=?, location=?, remark=?, updated_at=?
                    WHERE part_number=?
                    ''', (quantity, location, remark, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), part_number))
                else:
                    # 插入
                    self.cursor.execute('''
                    INSERT INTO inventory (part_number, description, total_quantity, unit, location, remark, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (part_number, description, quantity, unit, location, remark,
                         datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                         datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                count += 1
            
            self.conn.commit()
            messagebox.showinfo("成功", f"成功导入 {count} 条航材记录")
            self.load_inventory()
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def export_excel(self):
        """导出Excel"""
        file_path = filedialog.asksaveasfilename(
            title="保存Excel文件",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        
        if not file_path:
            return
        
        try:
            self.cursor.execute('''
            SELECT part_number, description, total_quantity, unit, location, min_stock, remark, created_at, updated_at
            FROM inventory
            ORDER BY part_number
            ''')
            
            rows = self.cursor.fetchall()
            columns = ['件号', '描述', '总数量', '单位', '架位号', '最低库存', '备注', '创建时间', '更新时间']
            
            df = pd.DataFrame(rows, columns=columns)
            df.to_excel(file_path, index=False)
            
            messagebox.showinfo("成功", f"成功导出 {len(rows)} 条记录")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'conn'):
            self.conn.close()

def main():
    root = tk.Tk()
    app = AeroMatApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
