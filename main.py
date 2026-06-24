#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北京维护中心乘务航材管理
AeroMat Inventory Management System
用于乘务航材消耗件管理

Version: 3.0
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import os
import sys
import shutil
import hashlib
from PIL import Image, ImageTk
import io

# 照片存储目录（程序运行目录下的 photos 文件夹）
PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'photos')


class AeroMatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("北京维护中心乘务航材管理")
        self.root.geometry("1400x800")

        # 确保照片目录存在
        os.makedirs(PHOTOS_DIR, exist_ok=True)

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

        # 创建库存主表（件号+架位共同唯一）
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            description TEXT NOT NULL,
            total_quantity REAL DEFAULT 0,
            unit TEXT DEFAULT '个',
            location TEXT,
            min_stock REAL DEFAULT 0,
            remark TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(part_number, location)
        )
        ''')

        # 兼容旧版数据库：从 v2.0 升级时补齐缺失的列
        for col_def in (
            "ALTER TABLE inventory ADD COLUMN description TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE inventory ADD COLUMN total_quantity REAL DEFAULT 0",
            "ALTER TABLE inventory ADD COLUMN unit TEXT DEFAULT '个'",
            "ALTER TABLE inventory ADD COLUMN min_stock REAL DEFAULT 0",
        ):
            try:
                self.cursor.execute(col_def)
            except Exception:
                pass  # 列已存在，忽略

        # 创建个体件表（每个具体件的追踪）
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            location TEXT,
            serial_number TEXT,
            expiry_date TEXT,
            last_check_date TEXT,
            status TEXT DEFAULT '正常',
            remark TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        ''')

        # 创建出入库记录表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            location TEXT,
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

        # 创建照片表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL,
            location TEXT,
            serial_number TEXT,
            file_path TEXT NOT NULL,
            file_name TEXT,
            description TEXT,
            created_at TEXT
        )
        ''')

        self.conn.commit()

    # ==================== 界面布局 ====================
    def create_widgets(self):
        """创建界面组件"""
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

        # === 标题栏 ===
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=2, pady=(0, 5))
        ttk.Label(title_frame, text="北京维护中心乘务航材管理",
                 font=('Arial', 14, 'bold')).pack()

        # === 搜索框 ===
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<KeyRelease>', lambda e: self.load_inventory())

        ttk.Button(search_frame, text="搜索", command=self.load_inventory).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="刷新", command=self.load_inventory).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="查看个体件",
                  command=self.show_items_detail).pack(side=tk.LEFT, padx=15)

        # === 库存表格 ===
        table_frame = ttk.Frame(main_frame)
        table_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        columns = ('件号', '描述', '总数量', '单位', '架位号', '最低库存', '有效期提醒', '备注')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=22)

        col_widths = {
            '件号': 130, '描述': 200, '总数量': 75, '单位': 55,
            '架位号': 100, '最低库存': 75, '有效期提醒': 130, '备注': 150
        }
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths[col],
                           anchor=tk.CENTER if col in ['总数量', '单位', '最低库存'] else tk.W)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<Double-1>', lambda e: self.show_items_detail())

        # === 按钮区 ===
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=8)

        ttk.Button(button_frame, text="新增航材", command=self.show_add_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑航材", command=self.show_edit_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除航材", command=self.delete_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="入库", command=self.show_in_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="出库", command=self.show_out_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="上传照片", command=self.show_photo_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="统计分析", command=self.show_statistics).pack(side=tk.LEFT, padx=5)

        # === 状态栏 ===
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var,
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

    # ==================== 数据加载 ====================
    def load_inventory(self):
        """加载库存数据"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        search_term = self.search_var.get().strip()
        if search_term:
            query = '''
            SELECT i.part_number, i.description, i.total_quantity, i.unit,
                   i.location, i.min_stock,
                   (SELECT MIN(ii.expiry_date) FROM inventory_items ii
                    WHERE ii.part_number=i.part_number AND ii.location=i.location
                    AND ii.status='正常') as earliest_expiry,
                   i.remark
            FROM inventory i
            WHERE (i.part_number LIKE ? OR i.description LIKE ? OR i.location LIKE ?)
            ORDER BY i.part_number, i.location
            '''
            self.cursor.execute(query, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        else:
            query = '''
            SELECT i.part_number, i.description, i.total_quantity, i.unit,
                   i.location, i.min_stock,
                   (SELECT MIN(ii.expiry_date) FROM inventory_items ii
                    WHERE ii.part_number=i.part_number AND ii.location=i.location
                    AND ii.status='正常') as earliest_expiry,
                   i.remark
            FROM inventory i
            ORDER BY i.part_number, i.location
            '''
            self.cursor.execute(query)

        rows = self.cursor.fetchall()
        today = datetime.now()

        for row in rows:
            expiry = row[6]
            expiry_alert = ''
            if expiry:
                try:
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
                    days_left = (expiry_date - today).days
                    if days_left < 0:
                        expiry_alert = f'⚠️ 已过期({expiry})'
                    elif days_left <= 30:
                        expiry_alert = f'🔴 {days_left}天({expiry})'
                    elif days_left <= 60:
                        expiry_alert = f'🟡 {days_left}天({expiry})'
                    elif days_left <= 90:
                        expiry_alert = f'🟢 {days_left}天({expiry})'
                    else:
                        expiry_alert = expiry
                except Exception:
                    expiry_alert = expiry

            self.tree.insert('', tk.END, values=(
                row[0], row[1], row[2], row[3],
                row[4] if row[4] else '-',
                row[5], expiry_alert, row[7] if row[7] else ''
            ))

        self.status_var.set(f"共 {len(rows)} 条记录")

    # ==================== 新增航材 ====================
    def show_add_dialog(self):
        """显示新增对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("新增航材")
        dialog.geometry("450x580")

        fields = {}
        row = 0

        self._add_field(dialog, fields, "件号 *", row, 0)
        fields['件号'].set('N/A')
        row += 1

        self._add_field(dialog, fields, "描述 *", row, 1)
        row += 1

        self._add_field(dialog, fields, "数量 *", row, 2)
        fields['数量'].set('1')
        row += 1

        self._add_field(dialog, fields, "单位", row, 3)
        fields['单位'].set('个')
        row += 1

        self._add_field(dialog, fields, "架位号", row, 4)
        row += 1

        self._add_field(dialog, fields, "最低库存", row, 5)
        fields['最低库存'].set('0')
        row += 1

        self._add_field(dialog, fields, "备注", row, 6)
        row += 1

        ttk.Separator(dialog, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        row += 1

        ttk.Label(dialog, text="批量添加个体件（可选）",
                 font=('Arial', 9, 'bold')).grid(
            row=row, column=0, columnspan=2, pady=4)
        row += 1

        self._add_field(dialog, fields, "件数量", row, 7)
        fields['件数量'].set('0')
        row += 1

        self._add_field(dialog, fields, "有效期(YYYY-MM-DD)", row, 8)
        row += 1

        def save():
            try:
                part_number = fields['件号'].get().strip()
                description = fields['描述'].get().strip()
                quantity = int(fields['数量'].get() or 1)
                unit = fields['单位'].get() or '个'
                location = fields['架位号'].get().strip()
                min_stock = float(fields['最低库存'].get() or 0)
                remark = fields['备注'].get().strip()
                item_count = int(fields['件数量'].get() or 0)
                expiry_date = fields['有效期'].get().strip()

                if not part_number or not description:
                    messagebox.showerror("错误", "件号和描述为必填项")
                    return

                # 处理N/A件号：生成虚拟件号
                if part_number.upper() == 'N/A':
                    part_number = self._make_na_part_number(description, location)

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 使用 INSERT OR REPLACE：件号+架位相同则更新数量
                self.cursor.execute('''
                INSERT INTO inventory (part_number, description, total_quantity, unit,
                                       location, min_stock, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(part_number, location) DO UPDATE SET
                    description=excluded.description,
                    total_quantity=total_quantity + excluded.total_quantity,
                    unit=excluded.unit,
                    min_stock=excluded.min_stock,
                    remark=excluded.remark,
                    updated_at=excluded.updated_at
                ''', (part_number, description, quantity, unit, location,
                     min_stock, remark, now, now))

                # 获取该件号+架位的现有最大序号
                self.cursor.execute('''
                SELECT MAX(serial_number) FROM inventory_items
                WHERE part_number=? AND location=?
                ''', (part_number, location))
                max_result = self.cursor.fetchone()[0]
                last_num = 0
                if max_result:
                    try:
                        parts = max_result.rsplit('-', 1)
                        last_num = int(parts[-1])
                    except Exception:
                        last_num = 0

                # 批量生成个体件（新增，不影响已有）
                new_items = max(item_count, quantity)
                for i in range(1, new_items + 1):
                    serial_num = f"{part_number}-{last_num + i:03d}"
                    self.cursor.execute('''
                    INSERT INTO inventory_items
                    (part_number, location, serial_number, expiry_date, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, '正常', ?, ?)
                    ''', (part_number, location, serial_num, expiry_date, now, now))

                self.conn.commit()

                msg = f"保存成功"
                if new_items > 0:
                    msg += f"\n已创建 {new_items} 个体件：{part_number}-{last_num+1:03d} ~ {part_number}-{last_num+new_items:03d}"
                messagebox.showinfo("成功", msg)
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))

        ttk.Button(dialog, text="保存", command=save).grid(row=row, column=0, padx=10, pady=20)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=20)

    def _add_field(self, dialog, fields, label, row, index):
        """在对话框中添加标签+输入框"""
        ttk.Label(dialog, text=label).grid(
            row=row, column=0, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        ttk.Entry(dialog, textvariable=var, width=30).grid(
            row=row, column=1, padx=10, pady=5)
        fields[index] = var

    # ==================== 编辑航材 ====================
    def show_edit_dialog(self):
        """显示编辑对话框"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要编辑的航材")
            return

        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        location = values[4] if values[4] != '-' else None

        self.cursor.execute(
            'SELECT * FROM inventory WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))',
            (part_number, location, location))
        record = self.cursor.fetchone()

        if not record:
            messagebox.showerror("错误", "找不到该航材记录")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑航材 - {part_number}")
        dialog.geometry("450x420")

        fields = {}
        row = 0

        ttk.Label(dialog, text=f"件号: {part_number}",
                 font=('Arial', 10, 'bold')).grid(
            row=row, column=0, columnspan=2, padx=10, pady=10)
        row += 1

        self._add_field(dialog, fields, "描述", row, '描述')
        fields['描述'].set(record[2])
        row += 1

        self._add_field(dialog, fields, "总数量", row, '数量')
        fields['数量'].set(str(record[3]))
        row += 1

        self._add_field(dialog, fields, "单位", row, '单位')
        fields['单位'].set(record[4] or '个')
        row += 1

        self._add_field(dialog, fields, "架位号", row, '架位')
        fields['架位'].set(record[5] or '')
        row += 1

        self._add_field(dialog, fields, "最低库存", row, '最低')
        fields['最低'].set(str(record[6] or 0))
        row += 1

        self._add_field(dialog, fields, "备注", row, '备注')
        fields['备注'].set(record[7] or '')
        row += 1

        def save():
            try:
                description = fields['描述'].get()
                total_qty = float(fields['数量'].get() or 0)
                unit = fields['单位'].get() or '个'
                new_location = fields['架位'].get().strip()
                min_stock = float(fields['最低'].get() or 0)
                remark = fields['备注'].get().strip()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 如果架位变化，需要特殊处理
                if (location or '') != (new_location or ''):
                    # 删除当前记录，将数量转移
                    self.cursor.execute('''
                    DELETE FROM inventory WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                    ''', (part_number, location, location))
                    # 新架位
                    self.cursor.execute('''
                    INSERT INTO inventory (part_number, description, total_quantity, unit, location,
                                           min_stock, remark, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(part_number, location) DO UPDATE SET
                        description=excluded.description,
                        total_quantity=total_quantity + excluded.total_quantity,
                        unit=excluded.unit,
                        min_stock=excluded.min_stock,
                        remark=excluded.remark,
                        updated_at=excluded.updated_at
                    ''', (part_number, description, total_qty, unit, new_location,
                         min_stock, remark, record[8], now))
                else:
                    self.cursor.execute('''
                    UPDATE inventory SET description=?, total_quantity=?, unit=?,
                                         min_stock=?, remark=?, updated_at=?
                    WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                    ''', (description, total_qty, unit, min_stock, remark, now,
                         part_number, location, location))

                self.conn.commit()
                messagebox.showinfo("成功", "更新成功")
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))

        ttk.Button(dialog, text="保存", command=save).grid(row=row, column=0, padx=10, pady=20)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=20)

    # ==================== 删除航材 ====================
    def delete_item(self):
        """删除航材"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要删除的航材")
            return

        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        location = values[4] if values[4] != '-' else None

        if messagebox.askyesno("确认",
            f"确定要删除 {part_number}（架位: {location or '未指定'}）吗？\n"
            "这将同时删除该位置所有个体件记录！"):
            self.cursor.execute('''
            DELETE FROM inventory_items WHERE part_number=? AND location=?
            ''', (part_number, location))
            self.cursor.execute('''
            DELETE FROM inventory WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
            ''', (part_number, location, location))
            self.conn.commit()
            messagebox.showinfo("成功", "删除成功")
            self.load_inventory()

    # ==================== 入库 ====================
    def show_in_dialog(self):
        """显示入库对话框"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择一行")
            return

        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        location = values[4] if values[4] != '-' else None

        dialog = tk.Toplevel(self.root)
        dialog.title(f"入库 - {part_number}")
        dialog.geometry("400x520")

        ttk.Label(dialog, text=f"件号: {part_number}",
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, padx=10, pady=8)
        ttk.Label(dialog, text=f"当前库存: {values[2]} {values[3]}").grid(
            row=1, column=0, columnspan=2, padx=10, pady=3)

        fields = {}
        row = 2
        self._add_field(dialog, fields, "入库数量 *", row, '数量')
        row += 1
        self._add_field(dialog, fields, "有效期(YYYY-MM-DD)", row, '有效期')
        row += 1
        self._add_field(dialog, fields, "架位号", row, '架位')
        if location:
            fields['架位'].set(location)
        row += 1
        self._add_field(dialog, fields, "经手人", row, '经手人')
        row += 1
        self._add_field(dialog, fields, "备注", row, '备注')
        row += 1

        def save():
            try:
                qty = int(fields['数量'].get())
                expiry = fields['有效期'].get().strip()
                shelf = fields['架位'].get().strip() or location
                operator = fields['经手人'].get().strip()
                remark = fields['备注'].get().strip()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if qty <= 0:
                    messagebox.showerror("错误", "入库数量必须大于0")
                    return

                # 获取该件号+架位下最大序号
                self.cursor.execute('''
                SELECT MAX(serial_number) FROM inventory_items
                WHERE part_number=? AND (location=? OR location IS NULL)
                ''', (part_number, shelf))
                max_result = self.cursor.fetchone()[0]
                last_num = 0
                if max_result:
                    try:
                        last_num = int(max_result.rsplit('-', 1)[-1])
                    except Exception:
                        last_num = 0

                # 插入个体件
                for i in range(1, qty + 1):
                    serial_num = f"{part_number}-{last_num + i:03d}"
                    self.cursor.execute('''
                    INSERT INTO inventory_items
                    (part_number, location, serial_number, expiry_date, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, '正常', ?, ?)
                    ''', (part_number, shelf, serial_num, expiry, now, now))

                # 更新总数量
                self.cursor.execute('''
                UPDATE inventory SET total_quantity=total_quantity+?, updated_at=?
                WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                ''', (qty, now, part_number, shelf, shelf))

                # 记录交易
                self.cursor.execute('''
                INSERT INTO transactions
                (part_number, location, trans_type, quantity, operator, purpose, trans_date, remark)
                VALUES (?, ?, 'IN', ?, ?, ?, ?, ?)
                ''', (part_number, shelf, qty, operator, remark, now, remark))

                self.conn.commit()
                messagebox.showinfo("成功",
                    f"入库成功！\n新增 {qty} 个体件\n"
                    f"件序号: {part_number}-{last_num+1:03d} ~ {part_number}-{last_num+qty:03d}")
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))

        ttk.Button(dialog, text="确定", command=save).grid(row=row, column=0, padx=10, pady=18)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=18)

    # ==================== 出库 ====================
    def show_out_dialog(self):
        """显示出库对话框"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择一行")
            return

        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        location = values[4] if values[4] != '-' else None

        self.cursor.execute('''
        SELECT serial_number, location, expiry_date FROM inventory_items
        WHERE part_number=? AND status='正常'
        ORDER BY expiry_date ASC, serial_number ASC
        ''', (part_number,))
        available_items = self.cursor.fetchall()

        if not available_items:
            messagebox.showerror("错误", "当前没有可用个体件")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"出库 - {part_number}")
        dialog.geometry("520x620")

        ttk.Label(dialog, text=f"件号: {part_number} | 描述: {values[1]}",
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, padx=10, pady=8)
        ttk.Label(dialog, text=f"当前库存: {values[2]} {values[3]}").grid(
            row=1, column=0, columnspan=2, padx=10, pady=3)

        row = 2
        ttk.Label(dialog, text="可用个体件:", font=('Arial', 9, 'bold')).grid(
            row=row, column=0, columnspan=2, padx=10, pady=4, sticky=tk.W)
        row += 1

        list_frame = ttk.Frame(dialog)
        list_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=5)
        listbox = tk.Listbox(list_frame, height=8, width=62)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        for it in available_items:
            serial, loc, expiry = it
            expiry_str = f"有效期: {expiry}" if expiry else "无有效期"
            loc_str = loc or '-'
            listbox.insert(tk.END, f"{serial} | 架位: {loc_str} | {expiry_str}")
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        row += 1

        qty_var = tk.StringVar(value='1')
        ttk.Label(dialog, text="出库数量").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(dialog, textvariable=qty_var, width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        operator_var = tk.StringVar()
        ttk.Label(dialog, text="领用人").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(dialog, textvariable=operator_var, width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        purpose_var = tk.StringVar()
        ttk.Label(dialog, text="用途").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(dialog, textvariable=purpose_var, width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        remark_var = tk.StringVar()
        ttk.Label(dialog, text="备注").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
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
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for i in range(qty):
                    serial = available_items[i][0]
                    self.cursor.execute('''
                    UPDATE inventory_items SET status='已领用', updated_at=?
                    WHERE part_number=? AND serial_number=?
                    ''', (now, part_number, serial))

                self.cursor.execute('''
                UPDATE inventory SET total_quantity=total_quantity-?, updated_at=?
                WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                ''', (qty, now, part_number, location, location))

                self.cursor.execute('''
                INSERT INTO transactions
                (part_number, location, trans_type, quantity, operator, purpose, trans_date, remark)
                VALUES (?, ?, 'OUT', ?, ?, ?, ?, ?)
                ''', (part_number, location, qty, operator, purpose, now, remark))

                self.conn.commit()
                messagebox.showinfo("成功", f"出库成功！减少 {qty} 件")
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))

        ttk.Button(dialog, text="确定", command=save).grid(row=row, column=0, padx=10, pady=18)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=18)

    # ==================== 个体件详情 ====================
    def show_items_detail(self):
        """显示个体件详情"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择一行")
            return

        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        location = values[4] if values[4] != '-' else None

        self.cursor.execute('''
        SELECT serial_number, location, expiry_date, last_check_date, status, remark, created_at
        FROM inventory_items
        WHERE part_number=?
        ORDER BY status, expiry_date ASC, serial_number ASC
        ''', (part_number,))
        items = self.cursor.fetchall()

        # 统计照片数量
        self.cursor.execute(
            'SELECT COUNT(*) FROM photos WHERE part_number=?', (part_number,))
        photo_count = self.cursor.fetchone()[0]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"个体件详情 - {part_number}")
        dialog.geometry("950x620")

        ttk.Label(dialog, text=f"件号: {part_number} | 架位: {location or '未指定'} | "
                 f"当前库存: {values[2]} {values[3]}",
                 font=('Arial', 10, 'bold')).pack(pady=6)

        if not items:
            ttk.Label(dialog, text="暂无个体件记录（该记录由Excel导入，数量仅记录在主表）").pack(pady=20)
            ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=10)
            return

        columns = ('件序号', '架位号', '有效期', '上次检查', '状态', '备注', '创建时间')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=18)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        today = datetime.now()
        for it in items:
            serial, shelf, expiry, check_date, status, remark, created = it
            expiry_status = expiry or '-'
            if expiry and status == '正常':
                try:
                    days_left = (datetime.strptime(expiry, '%Y-%m-%d') - today).days
                    if days_left < 0:
                        expiry_status = f"⚠️ 已过期({expiry})"
                    elif days_left <= 30:
                        expiry_status = f"🔴 {expiry}({days_left}天)"
                    elif days_left <= 60:
                        expiry_status = f"🟡 {expiry}({days_left}天)"
                except Exception:
                    pass
            tree.insert('', tk.END, values=(
                serial, shelf or '-', expiry_status, check_date or '-',
                status, remark or '-', created or '-'
            ))

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="编辑个体件", command=lambda: self._edit_single_item(tree, part_number, location)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="查看/上传照片",
                  command=lambda: self.show_photo_dialog(part_number=part_number, location=location)).pack(side=tk.LEFT, padx=5)
        if photo_count > 0:
            ttk.Label(btn_frame, text=f"📷 {photo_count} 张照片",
                     foreground='blue').pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Label(dialog, text=f"共 {len(items)} 个体件").pack(pady=4)

    def _edit_single_item(self, tree, part_number, location):
        """编辑选中的个体件"""
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("警告", "请选择要编辑的个体件")
            return
        item_data = tree.item(sel[0])
        serial = item_data['values'][0]
        self.cursor.execute(
            'SELECT * FROM inventory_items WHERE part_number=? AND serial_number=?',
            (part_number, serial))
        record = self.cursor.fetchone()
        if not record:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑个体件 - {serial}")
        dialog.geometry("420x400")
        fields = {}
        row = 0
        ttk.Label(dialog, text=f"件序号: {serial}",
                 font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, padx=10, pady=8)
        row += 1
        self._add_field(dialog, fields, "架位号", row, '架位')
        fields['架位'].set(record[2] or '')
        row += 1
        self._add_field(dialog, fields, "有效期", row, '有效期')
        fields['有效期'].set(record[3] or '')
        row += 1
        self._add_field(dialog, fields, "上次检查日期", row, '检查')
        fields['检查'].set(record[4] or '')
        row += 1
        self._add_field(dialog, fields, "状态", row, '状态')
        fields['状态'].set(record[5])
        ttk.Combobox(dialog, textvariable=fields['状态'],
                    values=['正常', '已领用', '已过期', '已报废'], width=28).grid(
            row=row, column=1, padx=10, pady=5)
        row += 1
        self._add_field(dialog, fields, "备注", row, '备注')
        fields['备注'].set(record[6] or '')
        row += 1
        def save():
            try:
                shelf = fields['架位'].get().strip()
                expiry = fields['有效期'].get().strip()
                check_date = fields['检查'].get().strip()
                status = fields['状态'].get()
                remark = fields['备注'].get().strip()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute('''
                UPDATE inventory_items SET location=?, expiry_date=?, last_check_date=?,
                                           status=?, remark=?, updated_at=?
                WHERE part_number=? AND serial_number=?
                ''', (shelf, expiry, check_date, status, remark, now, part_number, serial))
                self.conn.commit()
                messagebox.showinfo("成功", "更新成功")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("错误", str(e))
        ttk.Button(dialog, text="保存", command=save).grid(row=row, column=0, padx=10, pady=18)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=row, column=1, padx=10, pady=18)

    # ==================== 照片管理 ====================
    def show_photo_dialog(self, part_number=None, location=None):
        """照片管理对话框（支持从列表栏点击或个体件详情中调用）"""
        # 如果未指定件号，从当前选择获取
        if part_number is None:
            selection = self.tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请先在列表中选择一行")
                return
            item = self.tree.item(selection[0])
            part_number = item['values'][0]
            location = item['values'][4] if item['values'][4] != '-' else None

        dialog = tk.Toplevel(self.root)
        dialog.title(f"照片管理 - {part_number}")
        dialog.geometry("800x600")
        dialog.grab_set()

        # 顶部信息
        ttk.Label(dialog, text=f"件号: {part_number} | 架位: {location or '全部'}",
                 font=('Arial', 10, 'bold')).pack(pady=6)

        # 照片展示区（带滚动条）
        canvas_frame = ttk.Frame(dialog)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._refresh_photo_view(canvas_frame, part_number, location, dialog)

        # 底部按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=8)

        def do_upload():
            self._upload_photo(part_number, location)
            self._refresh_photo_view(canvas_frame, part_number, location, dialog)

        ttk.Button(btn_frame, text="📷 上传照片", command=do_upload).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=lambda: self._refresh_photo_view(
            canvas_frame, part_number, location, dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _refresh_photo_view(self, canvas_frame, part_number, location, dialog):
        """刷新照片展示区"""
        # 清除现有内容
        for widget in canvas_frame.winfo_children():
            widget.destroy()

        canvas = tk.Canvas(canvas_frame, bg='#f0f0f0')
        scrollbar_y = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar_x = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 查询照片
        if location:
            self.cursor.execute(
                'SELECT id, file_path, file_name, description, created_at FROM photos '
                'WHERE part_number=? AND location=? ORDER BY created_at DESC',
                (part_number, location))
        else:
            self.cursor.execute(
                'SELECT id, file_path, file_name, description, created_at FROM photos '
                'WHERE part_number=? ORDER BY created_at DESC',
                (part_number,))

        photos = self.cursor.fetchall()

        if not photos:
            ttk.Label(canvas, text="暂无照片，点击「上传照片」添加",
                     font=('Arial', 10), foreground='gray').pack(pady=40)
            canvas.configure(scrollregion=(0, 0, 600, 100))
            return

        # 每行3张，缩略图尺寸
        THUMB_W = 180
        THUMB_H = 160
        COLS = 3
        PAD = 10

        total_rows = (len(photos) + COLS - 1) // COLS
        canvas_width = COLS * (THUMB_W + PAD * 2)
        canvas_height = total_rows * (THUMB_H + 40 + PAD)

        canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))

        # 存储缩略图引用防止被垃圾回收
        dialog._thumbs = {}

        for idx, photo in enumerate(photos):
            photo_id, file_path, file_name, desc, created = photo
            col = idx % COLS
            row = idx // COLS
            x = col * (THUMB_W + PAD * 2) + PAD
            y = row * (THUMB_H + 40 + PAD) + PAD

            # 卡片背景
            card = tk.Frame(canvas, bg='white', bd=1, relief=tk.RAISED)
            canvas.create_window(x, y, window=card, width=THUMB_W, height=THUMB_H + 30)

            # 缩略图
            try:
                img = Image.open(file_path)
                img.thumbnail((THUMB_W - 10, THUMB_H - 10), Image.LANCZOS)
                photo_img = ImageTk.PhotoImage(img)
                dialog._thumbs[photo_id] = photo_img  # 保持引用
                lbl = tk.Label(card, image=photo_img, cursor='hand2', bg='white')
            except Exception:
                lbl = tk.Label(card, text=f"[图片\n无法显示]", bg='#ddd',
                             width=22, height=7, cursor='hand2')

            lbl.pack(pady=(4, 0))

            # 点击查看大图
            def view_full(fp=file_path):
                self._view_full_photo(fp)

            lbl.bind('<Button-1>', lambda e, fp=file_path: self._view_full_photo(fp))

            # 文件名 + 删除按钮
            info_frame = tk.Frame(card, bg='white')
            info_frame.pack(fill=tk.X, pady=2)
            fname = (file_name or os.path.basename(file_path))[:18]
            tk.Label(info_frame, text=fname, bg='white', fg='#555',
                   font=('Arial', 7)).pack(side=tk.LEFT)

            def delete_photo(pid=photo_id, fp=file_path, cfd=canvas_frame, loc=location):
                if messagebox.askyesno("确认", "确定要删除这张照片吗？"):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
                    self.cursor.execute('DELETE FROM photos WHERE id=?', (pid,))
                    self.conn.commit()
                    self._refresh_photo_view(cfd, part_number, loc, dialog)

            tk.Button(info_frame, text='×', command=delete_photo,
                     font=('Arial', 9), fg='red', bg='white',
                     bd=0, width=2, height=1).pack(side=tk.RIGHT)

    def _upload_photo(self, part_number, location):
        """上传照片"""
        file_path = filedialog.askopenfilename(
            title="选择照片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            # 生成唯一文件名
            now = datetime.now()
            ts = now.strftime('%Y%m%d%H%M%S')
            ext = os.path.splitext(file_path)[1].lower() or '.jpg'
            safe_pn = part_number.replace('/', '_').replace('\\', '_')
            safe_loc = (location or 'unknown').replace('/', '_').replace('\\', '_')
            new_name = f"{safe_pn}_{safe_loc}_{ts}{ext}"
            dest_path = os.path.join(PHOTOS_DIR, new_name)

            # 复制文件到photos目录
            shutil.copy2(file_path, dest_path)

            # 记录到数据库
            self.cursor.execute('''
            INSERT INTO photos (part_number, location, file_path, file_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (part_number, location, dest_path, new_name, now.strftime('%Y-%m-%d %H:%M:%S')))
            self.conn.commit()

            messagebox.showinfo("成功", f"照片已上传！\n文件名: {new_name}")
        except Exception as e:
            messagebox.showerror("错误", f"上传失败: {str(e)}")

    def _view_full_photo(self, file_path):
        """查看大图"""
        try:
            img = Image.open(file_path)
            win = tk.Toplevel(self.root)
            win.title(os.path.basename(file_path))
            # 限制最大尺寸
            max_w, max_h = 900, 700
            w, h = img.size
            ratio = min(max_w / w, max_h / h, 1)
            new_size = (int(w * ratio), int(h * ratio))
            img_large = img.resize(new_size, Image.LANCZOS)
            photo = ImageTk.PhotoImage(img_large)
            tk.Label(win, image=photo, cursor='hand2').pack()
            win._img_ref = photo
            win.bind('<Button-1>', lambda e: win.destroy())
            win.bind('<Escape>', lambda e: win.destroy())
        except Exception as e:
            messagebox.showerror("错误", f"无法显示图片: {str(e)}")

    # ==================== 低库存预警 ====================
    def show_low_stock(self):
        """显示低库存预警"""
        dialog = tk.Toplevel(self.root)
        dialog.title("低库存预警")
        dialog.geometry("900x450")

        self.cursor.execute('''
        SELECT part_number, description, total_quantity, unit, location, min_stock
        FROM inventory
        WHERE total_quantity <= min_stock AND min_stock > 0
        ORDER BY (total_quantity / NULLIF(min_stock, 0)) ASC
        ''')
        rows = self.cursor.fetchall()

        if not rows:
            ttk.Label(dialog, text="✅ 当前没有低库存预警", font=('Arial', 12)).pack(pady=30)
            ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=10)
            return

        columns = ('件号', '描述', '当前库存', '单位', '架位号', '最低库存', '缺口')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=15)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110 if col != '描述' else 200)
        for row in rows:
            gap = row[5] - row[2]
            tree.insert('', tk.END, values=row + (gap,))
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(dialog, text=f"⚠️ 共 {len(rows)} 项低库存预警",
                 foreground='red', font=('Arial', 11, 'bold')).pack(pady=5)
        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=5)

    # ==================== 有效期预警 ====================
    def show_expiry_alert(self):
        """显示有效期预警"""
        dialog = tk.Toplevel(self.root)
        dialog.title("有效期预警（未来90天）")
        dialog.geometry("1000x500")

        today = datetime.now()
        alert_date = (today + timedelta(days=90)).strftime('%Y-%m-%d')

        self.cursor.execute('''
        SELECT ii.part_number, ii.serial_number, ii.location, ii.expiry_date, ii.status
        FROM inventory_items ii
        WHERE ii.expiry_date IS NOT NULL AND ii.expiry_date != ''
          AND ii.expiry_date <= ? AND ii.status = '正常'
        ORDER BY ii.expiry_date ASC
        ''', (alert_date,))
        rows = self.cursor.fetchall()

        if not rows:
            ttk.Label(dialog, text="✅ 未来90天内没有到期航材", font=('Arial', 12)).pack(pady=30)
            ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=10)
            return

        columns = ('件号', '件序号', '架位号', '到期日期', '状态', '剩余天数')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=18)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150 if col in ('件号', '件序号') else 120)
        for row in rows:
            expiry = datetime.strptime(row[3], '%Y-%m-%d')
            days_left = (expiry - today).days
            icon = '⚠️' if days_left < 0 else ('🔴' if days_left <= 30 else '🟡')
            tree.insert('', tk.END, values=row + (f"{icon} {days_left}天",))
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(dialog, text=f"⚠️ 共 {len(rows)} 项即将到期",
                 foreground='red', font=('Arial', 11, 'bold')).pack(pady=5)
        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=5)

    # ==================== 统计分析 ====================
    def show_statistics(self):
        """显示统计分析"""
        dialog = tk.Toplevel(self.root)
        dialog.title("库存统计分析")
        dialog.geometry("700x580")

        stats_frame = ttk.Frame(dialog, padding=20)
        stats_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(stats_frame, text="库存统计概览",
                 font=('Arial', 14, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=(0, 15))

        self.cursor.execute('SELECT COUNT(*) FROM inventory')
        total_types = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT SUM(total_quantity) FROM inventory')
        total_items = self.cursor.fetchone()[0] or 0

        self.cursor.execute('SELECT COUNT(*) FROM inventory WHERE total_quantity <= min_stock AND min_stock > 0')
        low_stock_count = self.cursor.fetchone()[0]

        self.cursor.execute('''
        SELECT COUNT(*) FROM inventory_items
        WHERE expiry_date IS NOT NULL AND expiry_date != ''
          AND expiry_date <= date('now', '+90 days') AND status = '正常'
        ''')
        expiry_count = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM transactions')
        trans_count = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM photos')
        photo_count = self.cursor.fetchone()[0]

        stats = [
            ("航材种类数", total_types),
            ("库存总数量", total_items),
            ("低库存预警", low_stock_count),
            ("即将到期(90天)", expiry_count),
            ("交易记录数", trans_count),
            ("已上传照片", photo_count),
        ]
        for i, (label, value) in enumerate(stats):
            ttk.Label(stats_frame, text=label + ":",
                     font=('Arial', 11)).grid(row=i+1, column=0, padx=10, pady=6, sticky=tk.W)
            fg = 'red' if (i in (2, 3) and value > 0) else 'black'
            ttk.Label(stats_frame, text=str(value), font=('Arial', 11, 'bold'),
                     foreground=fg).grid(row=i+1, column=1, padx=10, pady=6, sticky=tk.W)

        ttk.Separator(stats_frame, orient=tk.HORIZONTAL).grid(
            row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        ttk.Label(stats_frame, text="最近30天出入库统计:",
                 font=('Arial', 12, 'bold')).grid(
            row=9, column=0, columnspan=2, sticky=tk.W, pady=(5, 8))

        self.cursor.execute('''
        SELECT trans_type, COUNT(*), SUM(quantity)
        FROM transactions WHERE trans_date >= date('now', '-30 days')
        GROUP BY trans_type
        ''')
        for trans in self.cursor.fetchall():
            label = "入库" if trans[0] == 'IN' else "出库"
            ttk.Label(stats_frame, text=f"{label}: {trans[1]}次, 共{trans[2]}件",
                     font=('Arial', 10)).grid(
                row=10 if trans[0] == 'IN' else 11,
                column=0, columnspan=2, sticky=tk.W, padx=20, pady=2)

        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=15)

    # ==================== Excel 导入（新版） ====================
    def import_excel(self):
        """
        导入Excel - 新版格式
        列顺序：件号、描述、数量、单位、架位号、备注
        去重逻辑：件号+架位号 组合唯一
        N/A航材：用 描述+架位号 生成虚拟件号
        相同件号、不同架位 = 各自独立导入
        """
        file_path = filedialog.askopenfilename(
            title="选择Excel文件",
            filetypes=[("Excel文件", "*.xlsx *.xls")]
        )
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path)
            # 列名标准化
            df.columns = [c.strip() for c in df.columns]

            # 支持新旧两种列名
            col_map = {}
            for expected in ['件号', '描述', '数量', '单位', '架位号', '备注']:
                for actual in df.columns:
                    if expected in actual:
                        col_map[expected] = actual
                        break

            missing = [c for c in ['件号', '描述', '数量'] if c not in col_map]
            if missing:
                messagebox.showerror("错误",
                    f"缺少必需列: {', '.join(missing)}\n"
                    "Excel表头应为：件号、描述、数量、单位、架位号、备注")
                return

            imported = 0
            skipped = 0
            na_items = 0
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for _, row in df.iterrows():
                # 读取字段
                part_number = str(row.get(col_map.get('件号', ''), '')).strip()
                description = str(row.get(col_map.get('描述', ''), '')).strip()
                quantity_raw = str(row.get(col_map.get('数量', ''), '0')).strip()
                unit = str(row.get(col_map.get('单位', ''), '个')).strip()
                location = str(row.get(col_map.get('架位号', ''), '')).strip()
                remark = str(row.get(col_map.get('备注', ''), '')).strip()

                # 解析数量（去掉"箱"等文字）
                try:
                    qty = float(quantity_raw.replace('箱', '').replace('个', '').strip())
                except Exception:
                    qty = 0.0

                if qty <= 0:
                    skipped += 1
                    continue

                if not description or description == 'nan':
                    skipped += 1
                    continue

                # 处理 N/A 件号
                is_na = (part_number.upper() in ('N/A', 'NA', '', 'nan'))
                if is_na:
                    part_number = self._make_na_part_number(description, location)
                    na_items += 1

                # 查询是否已存在（件号+架位号唯一）
                self.cursor.execute('''
                SELECT id, total_quantity FROM inventory
                WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                ''', (part_number, location, location))
                existing = self.cursor.fetchone()

                if existing:
                    # 累加数量（同一件号+同一架位）
                    self.cursor.execute('''
                    UPDATE inventory SET total_quantity=total_quantity+?, updated_at=?,
                                        description=COALESCE(NULLIF(description,''), excluded.description)
                    WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                    ''', (qty, now, part_number, location, location))
                    skipped += 1
                else:
                    # 插入新记录
                    self.cursor.execute('''
                    INSERT INTO inventory (part_number, description, total_quantity, unit,
                                           location, remark, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (part_number, description, qty, unit or '个', location or None,
                         remark, now, now))
                    imported += 1

                # 为该件号+架位生成个体件记录（每个Excel行生成对应数量的个体件）
                self.cursor.execute('''
                SELECT MAX(serial_number) FROM inventory_items
                WHERE part_number=? AND (location=? OR location IS NULL)
                ''', (part_number, location))
                max_result = self.cursor.fetchone()[0]
                last_num = 0
                if max_result:
                    try:
                        last_num = int(max_result.rsplit('-', 1)[-1])
                    except Exception:
                        last_num = 0

                for i in range(1, int(qty) + 1):
                    serial_num = f"{part_number}-{last_num + i:03d}"
                    self.cursor.execute('''
                    INSERT INTO inventory_items
                    (part_number, location, serial_number, status, created_at, updated_at)
                    VALUES (?, ?, ?, '正常', ?, ?)
                    ''', (part_number, location or None, serial_num, now, now))

            self.conn.commit()

            message = (f"导入完成！\n"
                      f"✅ 新增记录: {imported} 条\n"
                      f"🔄 累加数量: {skipped} 条（件号+架位已存在）\n"
                      f"📋 含N/A航材: {na_items} 条\n"
                      f"💡 相同件号不同架位已正确导入为独立记录")
            messagebox.showinfo("导入成功", message)
            self.load_inventory()

        except Exception as e:
            messagebox.showerror("错误", f"导入失败:\n{str(e)}")

    def _make_na_part_number(self, description, location):
        """
        为 N/A 件号的航材生成稳定的虚拟件号
        规则：NA_描述_架位号（去掉空格和特殊字符）
        """
        base = f"NA_{description}_{location or '未知架位'}"
        # 去掉特殊字符，只保留中文、字母、数字、下划线
        clean = ''
        for ch in base:
            if ch.isalnum() or ch in ('_', '-'):
                clean += ch
        # 限制长度（确保以NA_开头，便于识别）
        result = ('NA_' + clean)[:80] if clean else f"NA_{hashlib.md5(base.encode()).hexdigest()[:8]}"
        # 去掉开头重复的NA_NA_前缀
        if result.startswith('NA_NA_'):
            result = result[3:]  # 去掉开头的NA_
        return result

    # ==================== Excel 导出 ====================
    def export_excel(self):
        """导出Excel"""
        file_path = filedialog.asksaveasfilename(
            title="保存Excel文件",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx")]
        )
        if not file_path:
            return
        try:
            self.cursor.execute('''
            SELECT part_number, description, total_quantity, unit, location,
                   min_stock, remark, created_at, updated_at
            FROM inventory ORDER BY part_number, location
            ''')
            rows = self.cursor.fetchall()
            columns = ['件号', '描述', '总数量', '单位', '架位号',
                      '最低库存', '备注', '创建时间', '更新时间']
            df = pd.DataFrame(rows, columns=columns)
            df.to_excel(file_path, index=False)
            messagebox.showinfo("成功", f"已导出 {len(rows)} 条记录")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # ==================== 盘点 ====================
    def show_check_dialog(self):
        """显示盘点对话框"""
        messagebox.showinfo("盘点", "提示：选中某条航材后，点击「查看个体件」进行详细盘点\n"
                                 "可编辑个体件的状态、检查日期和备注")

    # ==================== 析构 ====================
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()


def main():
    root = tk.Tk()
    app = AeroMatApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
