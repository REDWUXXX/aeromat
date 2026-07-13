#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北京维护中心乘务航材管理
AeroMat Inventory Management System
用于乘务航材消耗件管理

Version: 3.2
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
from PIL import Image, ImageTk, ImageDraw
import io

# ============================================================
# 全局配色方案
# ============================================================
CLR_PRIMARY   = '#2563EB'   # 主色-蓝
CLR_SUCCESS   = '#16A34A'   # 成功-绿
CLR_DANGER    = '#DC2626'   # 危险-红
CLR_WARNING   = '#D97706'   # 警告-橙
CLR_BG        = '#F1F5F9'   # 页面背景浅灰
CLR_CARD      = '#FFFFFF'   # 卡片白
CLR_HEADER_BG = '#1E40AF'   # 顶部深蓝
CLR_HEADER_FG = '#FFFFFF'   # 顶部文字白
CLR_ROW_ODD   = '#F8FAFC'   # 奇数行淡灰
CLR_ROW_EVEN  = '#FFFFFF'   # 偶数行白
CLR_BORDER    = '#E2E8F0'   # 边框线
CLR_TEXT      = '#1E293B'   # 主文字
CLR_SUBTEXT   = '#64748B'   # 次要文字

# 数据库文件路径（程序运行目录下的 aeromat.db）
# 如需修改数据库名或路径，直接修改下面这行即可
DB_PATH = os.path.join(os.getcwd(), 'Database.db')

# 照片存储目录（程序运行目录下的 photos 文件夹）
PHOTOS_DIR = os.path.join(os.getcwd(), 'photos')  # 使用当前工作目录


class AeroMatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("北京维护中心乘务航材管理")
        self.root.geometry("1400x820")

        # 确保照片目录存在
        os.makedirs(PHOTOS_DIR, exist_ok=True)

        # 样式初始化
        self._setup_style()

        # 数据库初始化
        self.init_db()

        # 创建主界面
        self.create_widgets()

        # 加载数据
        self.load_inventory()

    def _setup_style(self):
        """全局样式配置"""
        style = ttk.Style(self.root)
        # 强制使用 clam 主题以保证 macOS/Linux 样式一致性
        try:
            style.theme_use('clam')
        except Exception:
            pass
        self.root.configure(bg=CLR_BG)

        # ---- 按钮样式 ----
        style.configure('Primary.TButton',
            font=('Arial', 10), padding=(12, 6),
            background=CLR_PRIMARY, foreground='white')
        style.map('Primary.TButton',
            background=[('active', '#1D4ED8'), ('pressed', '#1E40AF')],
            foreground=[('active', 'white'), ('pressed', 'white')])

        style.configure('Success.TButton',
            font=('Arial', 10), padding=(12, 6),
            background=CLR_SUCCESS)
        style.map('Success.TButton',
            background=[('active', '#15803D'), ('pressed', '#166534')])

        style.configure('Danger.TButton',
            font=('Arial', 10), padding=(12, 6),
            background=CLR_DANGER, foreground='white')
        style.map('Danger.TButton',
            background=[('active', '#B91C1C'), ('pressed', '#991B1B')])

        style.configure('Action.TButton',
            font=('Arial', 9), padding=(10, 4),
            background=CLR_PRIMARY, foreground='white')
        style.map('Action.TButton',
            background=[('active', '#1D4ED8')])

        style.configure('Flat.TButton',
            font=('Arial', 9), padding=(8, 4))

        # ---- Treeview 样式 ----
        style.configure('Treeview',
            background=CLR_CARD,
            foreground=CLR_TEXT,
            fieldbackground=CLR_CARD,
            rowheight=28,
            font=('Arial', 10))
        style.configure('Treeview.Heading',
            background=CLR_HEADER_BG,
            foreground=CLR_HEADER_FG,
            font=('Arial', 10, 'bold'),
            padding=(8, 6))
        style.map('Treeview',
            background=[('selected', '#DBEAFE')],
            foreground=[('selected', CLR_PRIMARY)])
        # 强制表头前景色（防止 macOS 默认白色覆盖）
        style.map('Treeview.Heading',
            background=[('!active', CLR_HEADER_BG), ('active', '#1E40AF')],
            foreground=[('!active', CLR_HEADER_FG), ('active', '#FFFFFF')])

        # ---- Frame / Label ----
        style.configure('Card.TFrame', background=CLR_CARD)
        style.configure('Title.TLabel',
            font=('Arial', 14, 'bold'),
            foreground=CLR_TEXT, background=CLR_BG)
        style.configure('Sub.TLabel',
            font=('Arial', 9),
            foreground=CLR_SUBTEXT, background=CLR_BG)
        style.configure('Badge.TLabel',
            font=('Arial', 8),
            foreground='white', background=CLR_PRIMARY)

    def init_db(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(DB_PATH)
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
            updated_at TEXT
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

        # 查询菜单
        query_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="查询", menu=query_menu)
        query_menu.add_command(label="低库存预警", command=self.show_low_stock)
        query_menu.add_command(label="有效期预警", command=self.show_expiry_alert)
        query_menu.add_separator()
        query_menu.add_command(label="统计分析", command=self.show_statistics)

        # ---- 顶部深蓝标题栏 ----
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)  # 主框架可伸缩，标题栏固定

        header_frame = tk.Frame(self.root, bg=CLR_HEADER_BG, height=52)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        header_frame.grid_propagate(False)  # 固定高度，不被内容撑开
        header_frame.columnconfigure(0, weight=1)

        tk.Label(header_frame, text="✈  北京维护中心乘务航材管理",
                 font=('Arial', 16, 'bold'),
                 bg=CLR_HEADER_BG, fg='white').pack(side=tk.LEFT, padx=18, pady=12)
        tk.Label(header_frame, text="ver3.4",
                 font=('Arial', 9),
                 bg=CLR_HEADER_BG, fg='#93C5FD').pack(side=tk.RIGHT, padx=18, pady=12)

        # 主框架（标题栏下方）
        main_frame = ttk.Frame(self.root, padding="12")
        main_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.configure(style='Card.TFrame')

        # === 按钮区（固定在顶部） ===
        btn_card = tk.Frame(main_frame, bg=CLR_CARD, bd=1, relief=tk.GROOVE,
                             highlightthickness=1, highlightcolor=CLR_BORDER)
        btn_card.pack(fill=tk.X, pady=(0, 10))

        # 第一行功能按钮
        row1 = tk.Frame(btn_card, bg=CLR_CARD)
        row1.pack(fill=tk.X, padx=12, pady=(10, 4))

        def plain_btn(parent, text, cmd):
            b = ttk.Button(parent, text=text, command=cmd)
            b.pack(side=tk.LEFT, padx=4)
            return b

        plain_btn(row1, "➕ 新增航材", self.show_add_dialog)
        plain_btn(row1, "✏ 编辑航材", self.show_edit_dialog)
        plain_btn(row1, "🗑 删除航材", self.delete_item)
        plain_btn(row1, "📥 入库", self.show_in_dialog)
        plain_btn(row1, "📤 出库", self.show_out_dialog)
        plain_btn(row1, "📷 上传照片", self.show_photo_dialog)
        plain_btn(row1, "📋 出入库记录", self.show_transaction_log)
        plain_btn(row1, "ℹ 关于", self.show_about)

        # === 搜索框卡片 ===
        search_card = tk.Frame(main_frame, bg=CLR_CARD, bd=1, relief=tk.GROOVE,
                                highlightthickness=1, highlightcolor=CLR_BORDER)
        search_card.pack(fill=tk.X, pady=(0, 10))
        search_card.columnconfigure(1, weight=1)

        tk.Label(search_card, text="🔍", font=('Arial', 14), bg=CLR_CARD).grid(
            row=0, column=0, padx=(12, 4), pady=10, sticky='e')
        tk.Label(search_card, text="搜索航材", font=('Arial', 9), bg=CLR_CARD,
                 fg=CLR_SUBTEXT).grid(row=0, column=1, sticky='w', padx=(0, 8))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_card, textvariable=self.search_var, font=('Arial', 11), width=24)
        search_entry.grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=8)
        search_entry.bind('<KeyRelease>', lambda e: self.load_inventory())

        ttk.Button(search_card, text="搜索", command=self.load_inventory).grid(
            row=0, column=2, padx=(4, 4), pady=8)
        ttk.Button(search_card, text="刷新", command=self.load_inventory).grid(
            row=0, column=3, padx=(4, 8), pady=8)

        # === 排序控件 ===
        sort_card = tk.Frame(main_frame, bg=CLR_CARD, bd=1, relief=tk.GROOVE,
                              highlightthickness=1, highlightcolor=CLR_BORDER)
        sort_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(sort_card, text="排序方式", font=('Arial', 9), bg=CLR_CARD,
                 fg=CLR_SUBTEXT).pack(side=tk.LEFT, padx=(12, 6), pady=8)

        self.sort_field = tk.StringVar(value='件号')
        sort_options = ['件号', '描述', '总数量', '架位号', '最低库存']
        sort_menu = ttk.Combobox(sort_card, textvariable=self.sort_field,
                                  values=sort_options, state='readonly', width=10, font=('Arial', 9))
        sort_menu.pack(side=tk.LEFT, padx=(0, 6), pady=8)
        sort_menu.bind('<<ComboboxSelected>>', lambda e: self.load_inventory())

        self.sort_order = tk.StringVar(value='升序')
        order_menu = ttk.Combobox(sort_card, textvariable=self.sort_order,
                                   values=['升序', '降序'], state='readonly', width=6, font=('Arial', 9))
        order_menu.pack(side=tk.LEFT, padx=(0, 6), pady=8)
        order_menu.bind('<<ComboboxSelected>>', lambda e: self.load_inventory())

        ttk.Button(sort_card, text="排序", command=self.load_inventory).pack(
            side=tk.LEFT, padx=(0, 12), pady=8)

        # === 库存表格卡片 ===
        table_card = tk.Frame(main_frame, bg=CLR_CARD, bd=1, relief=tk.GROOVE,
                               highlightthickness=1, highlightcolor=CLR_BORDER)
        table_card.pack(fill=tk.BOTH, expand=True)

        columns = ('件号', '描述', '总数量', '单位', '架位号', '最低库存', '有效期提醒', '备注', '照片')
        self.tree = ttk.Treeview(table_card, columns=columns, show='headings', height=22)

        col_widths = {
            '件号': 130, '描述': 200, '总数量': 75, '单位': 55,
            '架位号': 100, '最低库存': 75, '有效期提醒': 130, '备注': 150,
            '照片': 80
        }
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths[col],
                           anchor=tk.CENTER if col in ['总数量', '单位', '最低库存'] else tk.W)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0), pady=1)
        scrollbar = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=1)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<Double-1>', lambda e: self.show_items_detail())

        # 单击照片列打开图库
        self.tree.bind('<ButtonRelease-1>', self._on_tree_click)

        # 隔行变色
        self.tree.tag_configure('oddrow', background=CLR_ROW_ODD)
        self.tree.tag_configure('evenrow', background=CLR_ROW_EVEN)
        self.tree.tag_configure('low_stock', background='#FEE2E2')  # 淡红色背景

        # === 状态栏 ===
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(main_frame, textvariable=self.status_var,
                              bg=CLR_CARD, fg=CLR_SUBTEXT,
                              font=('Arial', 9), anchor='w',
                              padx=14, pady=6)
        status_bar.pack(fill=tk.X, pady=(6, 0))

    # ==================== 数据加载 ==================
    def _get_sort_clause(self):
        """根据排序设置生成 ORDER BY 子句"""
        # 排序字段映射：显示名 → SQL列名
        field_map = {
            '件号': 'i.part_number',
            '描述': 'i.description',
            '总数量': 'CAST(i.total_quantity AS REAL)',
            '架位号': 'i.location',
            '最低库存': 'CAST(i.min_stock AS REAL)',
        }
        sql_field = field_map.get(self.sort_field.get(), 'i.part_number')
        direction = 'DESC' if self.sort_order.get() == '降序' else 'ASC'
        # 数字字段降序时用 NULLS LAST 处理空值
        if self.sort_field.get() in ('总数量', '最低库存'):
            return f'ORDER BY {sql_field} {direction} NULLS LAST'
        return f'ORDER BY {sql_field} {direction}'

    def load_inventory(self):
        """加载库存数据"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        order_clause = self._get_sort_clause()
        search_term = self.search_var.get().strip()
        if search_term:
            query = f'''
            SELECT i.part_number, i.description, i.total_quantity, i.unit,
                   i.location, i.min_stock, i.remark
            FROM inventory i
            WHERE (i.part_number LIKE ? OR i.description LIKE ? OR i.location LIKE ?)
            {order_clause}
            '''
            self.cursor.execute(query, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        else:
            query = f'''
            SELECT i.part_number, i.description, i.total_quantity, i.unit,
                   i.location, i.min_stock, i.remark
            FROM inventory i
            {order_clause}
            '''
            self.cursor.execute(query)

        rows = self.cursor.fetchall()
        today = datetime.now()

        for idx, row in enumerate(rows):
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

            # 查询该件号是否有照片
            if row[4] and row[4] != 'N/A':
                self.cursor.execute('SELECT COUNT(*) FROM photos WHERE part_number=? AND location=?', (row[0], row[4]))
            else:
                self.cursor.execute('SELECT COUNT(*) FROM photos WHERE part_number=?', (row[0],))
            photo_count = self.cursor.fetchone()[0]
            photo_text = f"📷 {photo_count} 管理照片"

            tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
            # 低库存预警：红色背景标记
            tags = (tag,)
            if row[2] <= row[5]:  # total_quantity <= min_stock
                tags = (tag, 'low_stock')
            self.tree.insert('', tk.END, tags=tags, values=(
                row[0], row[1], row[2], row[3],
                row[4] if row[4] else '-',
                row[5], expiry_alert, row[6] if len(row) > 6 and row[6] else '',
                photo_text
            ))

        self.status_var.set(f"共 {len(rows)} 条记录")

    # ==================== 新增航材 ====================
    def show_add_dialog(self):
        """显示新增对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("✚ 新增航材")
        dialog.geometry("560x780")
        dialog.configure(bg='#F1F5F9')
        dialog.grab_set()
        dialog.transient(self.root)

        # 居中
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (560 // 2)
        y = (dialog.winfo_screenheight() // 2) - (780 // 2)
        dialog.geometry(f"560x780+{x}+{y}")

        # 列宽权重
        dialog.columnconfigure(1, weight=1)

        fields = {}
        row = 0

        fields['件号'] = self._add_field(dialog, fields, "件号 *", row)
        fields['件号'].set('N/A')
        row += 1

        fields['描述'] = self._add_field(dialog, fields, "描述 *", row)
        row += 1

        fields['数量'] = self._add_field(dialog, fields, "数量 *", row)
        fields['数量'].set('1')
        row += 1

        fields['单位'] = self._add_field(dialog, fields, "单位", row)
        fields['单位'].set('个')
        row += 1

        fields['架位号'] = self._add_field(dialog, fields, "架位号", row)
        row += 1

        fields['最低库存'] = self._add_field(dialog, fields, "最低库存", row)
        fields['最低库存'].set('0')
        row += 1

        fields['备注'] = self._add_field(dialog, fields, "备注", row)
        row += 1

        ttk.Separator(dialog, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        row += 1

        ttk.Label(dialog, text="批量添加个体件（可选）",
                 font=('Arial', 9, 'bold')).grid(
            row=row, column=0, columnspan=2, pady=4)
        row += 1

        fields['件数量'] = self._add_field(dialog, fields, "件数量", row)
        fields['件数量'].set('0')
        row += 1

        fields['有效期'] = self._add_field(dialog, fields, "有效期(YYYY-MM-DD)", row)
        row += 1

        def save():
            try:
                part_number = fields['件号'].get().strip()
                description = fields['描述'].get().strip()
                quantity = int(fields['数量'].get() or 1)
                unit = fields['单位'].get() or '个'
                location = fields['架位号'].get().strip()
                min_stock = float(fields['最低库存'].get() or 0)
                # 如果未设置最低库存，自动计算为总数量的20%
                if min_stock == 0:
                    min_stock = max(1, int(quantity * 0.2))
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

                # 件号+架位相同则累加数量，不同则新增记录
                self.cursor.execute('''
                SELECT id, total_quantity FROM inventory
                WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                ''', (part_number, location, location))
                existing = self.cursor.fetchone()
                if existing:
                    self.cursor.execute('''
                    UPDATE inventory SET description=?, total_quantity=total_quantity+?,
                                        unit=?, min_stock=?, remark=?, updated_at=?
                    WHERE id=?
                    ''', (description, quantity, unit, min_stock, remark, now, existing[0]))
                else:
                    self.cursor.execute('''
                    INSERT INTO inventory (part_number, description, total_quantity, unit,
                                           location, min_stock, remark, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (part_number, description, quantity, unit, location,
                         min_stock, remark, now, now))

                self.conn.commit()

                messagebox.showinfo("成功", "保存成功")
                dialog.destroy()
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("错误", str(e))

        btn_row = tk.Frame(dialog, bg="#F8FAFC", height=52)
        btn_row.grid(row=row, column=0, columnspan=2, sticky="ew")
        btn_row.pack_propagate(False)
        ttk.Button(btn_row, text="💾 保存", command=save).pack(side=tk.LEFT, padx=12, pady=10)
        ttk.Button(btn_row, text="✕ 取消", command=dialog.destroy).pack(side=tk.LEFT, padx=8, pady=10)
        row += 1

    def _add_field(self, dialog, fields, label, row, col_label=0, col_entry=1):
        """在对话框中添加标签+输入框"""
        ttk.Label(dialog, text=label).grid(
            row=row, column=col_label, padx=10, pady=5, sticky=tk.W)
        var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=var, width=36)
        entry.grid(row=row, column=col_entry, padx=10, pady=5, sticky=tk.EW)
        return var

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
        dialog.title(f"✏ 编辑航材 - {part_number}")
        dialog.geometry("560x800")
        dialog.configure(bg='#F1F5F9')
        dialog.grab_set()
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (560 // 2)
        y = (dialog.winfo_screenheight() // 2) - (800 // 2)
        dialog.geometry(f"560x800+{x}+{y}")
        dialog.columnconfigure(1, weight=1)

        fields = {}
        row = 0

        ttk.Label(dialog, text=f"件号: {part_number}",
                 font=('Arial', 10, 'bold')).grid(
            row=row, column=0, columnspan=2, padx=10, pady=10)
        row += 1

        fields['描述'] = self._add_field(dialog, fields, "描述", row)
        fields['描述'].set(record[2])
        row += 1

        fields['数量'] = self._add_field(dialog, fields, "总数量", row)
        fields['数量'].set(str(record[3]))
        row += 1

        fields['单位'] = self._add_field(dialog, fields, "单位", row)
        fields['单位'].set(record[4] or '个')
        row += 1

        fields['架位'] = self._add_field(dialog, fields, "架位号", row)
        fields['架位'].set(record[5] or '')
        row += 1

        fields['最低'] = self._add_field(dialog, fields, "最低库存", row)
        fields['最低'].set(str(record[6] or 0))
        row += 1

        fields['备注'] = self._add_field(dialog, fields, "备注", row)
        fields['备注'].set(record[7] or '')
        row += 1

        def save():
            try:
                description = fields['描述'].get()
                total_qty = float(fields['数量'].get() or 0)
                unit = fields['单位'].get() or '个'
                new_location = fields['架位'].get().strip()
                min_stock = float(fields['最低'].get() or 0)
                # 如果未设置最低库存，自动计算为总数量的20%
                if min_stock == 0:
                    min_stock = max(1, int(total_qty * 0.2))
                remark = fields['备注'].get().strip()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 如果架位变化，需要特殊处理
                if (location or '') != (new_location or ''):
                    # 删除当前记录
                    self.cursor.execute('''
                    DELETE FROM inventory WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                    ''', (part_number, location, location))
                    # 新架位：先查是否存在
                    self.cursor.execute('''
                    SELECT id FROM inventory
                    WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                    ''', (part_number, new_location, new_location))
                    existing = self.cursor.fetchone()
                    if existing:
                        self.cursor.execute('''
                        UPDATE inventory SET description=?, total_quantity=total_quantity+?,
                                            unit=?, min_stock=?, remark=?, updated_at=?
                        WHERE id=?
                        ''', (description, total_qty, unit, min_stock, remark, now, existing[0]))
                    else:
                        self.cursor.execute('''
                        INSERT INTO inventory (part_number, description, total_quantity, unit, location,
                                               min_stock, remark, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        # 按钮行（在 save 函数定义后创建）
        btn_frame = tk.Frame(dialog, bg="#F8FAFC", height=60)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(20, 0))
        ttk.Button(btn_frame, text="💾 保存", command=save).pack(side=tk.LEFT, padx=20, pady=15)
        ttk.Button(btn_frame, text="✕ 取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10, pady=15)

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
            f"确定要删除 {part_number}（架位: {location or '未指定'}）吗？"):
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
        dialog.title(f"📥 入库 - {part_number}")
        dialog.geometry("400x520")

    # ==================== 入库 ====================
    def show_in_dialog(self):
        """显示入库对话框（简化版：只按数量管理）"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择一行")
            return

        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        location = values[4] if values[4] != '-' else None

        dialog = tk.Toplevel(self.root)
        dialog.title(f"📥 入库 - {part_number}")
        dialog.geometry("480x520")
        dialog.transient(self.root)
        dialog.grab_set()

        # 信息区
        info_frame = ttk.Frame(dialog, padding=12)
        info_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(info_frame, text=f"件号: {part_number}", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"描述: {values[1]}").pack(anchor=tk.W, pady=2)
        ttk.Label(info_frame, text=f"架位: {values[4]}").pack(anchor=tk.W, pady=2)
        ttk.Label(info_frame, text=f"当前库存: {values[2]} {values[3]}", foreground="blue").pack(anchor=tk.W, pady=4)

        row = 1
        fields = {}
        fields['数量'] = self._add_field(dialog, fields, "入库数量 *", row)
        row += 1
        fields['有效期'] = self._add_field(dialog, fields, "有效期(YYYY-MM-DD)", row)
        row += 1
        fields['架位'] = self._add_field(dialog, fields, "架位号", row)
        if location:
            fields['架位'].set(location)
        row += 1
        fields['经手人'] = self._add_field(dialog, fields, "经手人", row)
        row += 1
        fields['备注'] = self._add_field(dialog, fields, "备注", row)
        row += 1

        def save():
            try:
                qty = float(fields['数量'].get())
                expiry = fields['有效期'].get().strip()
                shelf = fields['架位'].get().strip() or location
                operator = fields['经手人'].get().strip()
                remark = fields['备注'].get().strip()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if qty <= 0:
                    messagebox.showerror("错误", "入库数量必须大于0")
                    return

                # 只更新总数量（不生成个体件）
                self.cursor.execute('''
                UPDATE inventory SET total_quantity=total_quantity+?, updated_at=?
                WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                ''', (qty, now, part_number, shelf, shelf))

                # 获取描述信息
                self.cursor.execute('SELECT description FROM inventory WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL)) LIMIT 1',
                                 (part_number, shelf, shelf))
                desc_result = self.cursor.fetchone()
                desc = desc_result[0] if desc_result else ''

                # 记录交易
                self.cursor.execute('''
                INSERT INTO transactions
                (part_number, location, description, trans_type, quantity, operator, purpose, trans_date, remark)
                VALUES (?, ?, ?, 'IN', ?, ?, ?, ?, ?)
                ''', (part_number, shelf, desc, qty, operator, remark, now, remark))

                self.conn.commit()
                messagebox.showinfo("成功", f"入库成功！\n架位 {shelf} 增加 {qty} {values[3]}")
                dialog.destroy()
                self.load_inventory()
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数量")
            except Exception as e:
                messagebox.showerror("错误", str(e))

        # 按钮区
        btn_row = tk.Frame(dialog, bg="#F8FAFC", height=52)
        btn_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        btn_row.pack_propagate(False)
        ttk.Button(btn_row, text="💾 确定入库", command=save).pack(side=tk.LEFT, padx=12, pady=10)
        ttk.Button(btn_row, text="✕ 取消", command=dialog.destroy).pack(side=tk.LEFT, padx=8, pady=10)
    # ==================== 出库 ====================
    def show_out_dialog(self):
        """显示出库对话框（简化版：只按数量管理）"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择一行")
            return

        item = self.tree.item(selection[0])
        values = item['values']
        part_number = values[0]
        location = values[4] if values[4] != '-' else None
        current_qty = float(values[2])  # 当前架位的库存数量

        dialog = tk.Toplevel(self.root)
        dialog.title(f"📤 出库 - {part_number}")
        dialog.geometry("480x480")
        dialog.transient(self.root)
        dialog.grab_set()

        # 信息区
        info_frame = ttk.Frame(dialog, padding=12)
        info_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(info_frame, text=f"件号: {part_number}", font=('Arial', 11, 'bold')).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"描述: {values[1]}").pack(anchor=tk.W, pady=2)
        ttk.Label(info_frame, text=f"架位: {values[4]}").pack(anchor=tk.W, pady=2)
        ttk.Label(info_frame, text=f"当前库存: {current_qty} {values[3]}", foreground="blue").pack(anchor=tk.W, pady=4)

        row = 1
        # 出库数量
        ttk.Label(dialog, text="出库数量:").grid(row=row, column=0, padx=12, pady=6, sticky=tk.W)
        qty_var = tk.StringVar(value='1')
        qty_entry = ttk.Entry(dialog, textvariable=qty_var, width=20)
        qty_entry.grid(row=row, column=1, padx=12, pady=6, sticky=tk.W)
        row += 1

        # 领用人
        ttk.Label(dialog, text="领用人:").grid(row=row, column=0, padx=12, pady=6, sticky=tk.W)
        operator_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=operator_var, width=20).grid(row=row, column=1, padx=12, pady=6, sticky=tk.W)
        row += 1

        # 用途
        ttk.Label(dialog, text="用途:").grid(row=row, column=0, padx=12, pady=6, sticky=tk.W)
        purpose_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=purpose_var, width=20).grid(row=row, column=1, padx=12, pady=6, sticky=tk.W)
        row += 1

        # 备注
        ttk.Label(dialog, text="备注:").grid(row=row, column=0, padx=12, pady=6, sticky=tk.W)
        remark_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=remark_var, width=20).grid(row=row, column=1, padx=12, pady=6, sticky=tk.W)
        row += 1

        def save():
            try:
                qty = float(qty_var.get())
                if qty <= 0:
                    messagebox.showerror("错误", "出库数量必须大于0")
                    return
                if qty > current_qty:
                    messagebox.showerror("错误", f"库存不足！\n当前架位库存: {current_qty} {values[3]}")
                    return
                operator = operator_var.get().strip()
                purpose = purpose_var.get().strip()
                remark = remark_var.get().strip()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 只减少当前架位的库存
                self.cursor.execute('''
                UPDATE inventory SET total_quantity=total_quantity-?, updated_at=?
                WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL))
                ''', (qty, now, part_number, location, location))

                # 获取描述信息
                self.cursor.execute('SELECT description FROM inventory WHERE part_number=? AND (location=? OR (location IS NULL AND ? IS NULL)) LIMIT 1',
                                 (part_number, location, location))
                desc_result = self.cursor.fetchone()
                desc = desc_result[0] if desc_result else ''

                # 记录交易
                self.cursor.execute('''
                INSERT INTO transactions
                (part_number, location, description, trans_type, quantity, operator, purpose, trans_date, remark)
                VALUES (?, ?, ?, 'OUT', ?, ?, ?, ?, ?)
                ''', (part_number, location, desc, qty, operator, purpose, now, remark))

                self.conn.commit()
                messagebox.showinfo("成功", f"出库成功！\n架位 {values[4]} 减少 {qty} {values[3]}")
                dialog.destroy()
                self.load_inventory()
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数量")
            except Exception as e:
                messagebox.showerror("错误", str(e))

        # 按钮区
        btn_row = tk.Frame(dialog, bg="#F8FAFC", height=52)
        btn_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        btn_row.pack_propagate(False)
        ttk.Button(btn_row, text="💾 确定出库", command=save).pack(side=tk.LEFT, padx=12, pady=10)
        ttk.Button(btn_row, text="✕ 取消", command=dialog.destroy).pack(side=tk.LEFT, padx=8, pady=10)
    def _on_tree_click(self, event):
        """单击主表格：点到照片列就打开照片图库"""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        # 照片列是第9列（#9），columns 索引从1开始
        if col == "#9":
            item = self.tree.identify_row(event.y)
            if not item:
                return
            values = self.tree.item(item, "values")
            part_number = values[0]
            location = values[4] if values[4] != '-' else None
            self.show_photo_dialog(part_number, location)

    # ==================== 个体件详情 ====================
    def _edit_single_item(self, tree, part_number, location):
        """编辑选中的个体件"""
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("警告", "请选择要编辑的个体件")
            return
        item_data = tree.item(sel[0])
        serial = item_data['values'][0]
        # 当前版本已移除 inventory_items 表，个体件编辑功能待实现
        messagebox.showinfo("提示", "个体件编辑功能在当前版本中暂不可用")
        return
        record = None  # unreachable, kept for syntax
        dialog = tk.Toplevel(self.root)
        dialog.title(f"✏ 编辑个体件 - {serial}")
        dialog.geometry("460x480")
        dialog.configure(bg='#F1F5F9')
        dialog.grab_set()
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (460 // 2)
        y = (dialog.winfo_screenheight() // 2) - (480 // 2)
        dialog.geometry(f"460x480+{x}+{y}")
        dialog.columnconfigure(1, weight=1)
        fields = {}
        row = 0
        ttk.Label(dialog, text=f"件序号: {serial}",
                 font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, padx=10, pady=8)
        row += 1
        fields['架位'] = self._add_field(dialog, fields, "架位号", row)
        fields['架位'].set(record[2] or '')
        row += 1
        fields['有效期'] = self._add_field(dialog, fields, "有效期", row)
        fields['有效期'].set(record[3] or '')
        row += 1
        fields['检查'] = self._add_field(dialog, fields, "上次检查日期", row)
        fields['检查'].set(record[4] or '')
        row += 1
        fields['状态'] = self._add_field(dialog, fields, "状态", row)
        fields['状态'].set(record[5])
        ttk.Combobox(dialog, textvariable=fields['状态'],
                    values=['正常', '已领用', '已过期', '已报废'], width=28).grid(
            row=row, column=1, padx=10, pady=5)
        row += 1
        fields['备注'] = self._add_field(dialog, fields, "备注", row)
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
                                           status=?, remark=?, updated_at=?
                WHERE part_number=? AND serial_number=?
                ''', (shelf, expiry, check_date, status, remark, now, part_number, serial))
                self.conn.commit()
                messagebox.showinfo("成功", "更新成功")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("错误", str(e))
        btn_row = tk.Frame(dialog, bg="#F8FAFC", height=52)
        btn_row.grid(row=row, column=0, columnspan=2, sticky="ew")
        btn_row.pack_propagate(False)
        ttk.Button(btn_row, text="💾 保存", command=save).pack(side=tk.LEFT, padx=12, pady=10)
        ttk.Button(btn_row, text="✕ 取消", command=dialog.destroy).pack(side=tk.LEFT, padx=8, pady=10)

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
        dialog.title(f"📷 照片管理 - {part_number}")
        dialog.geometry("1020x740")
        dialog.configure(bg=CLR_BG)
        dialog.grab_set()
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (1020 // 2)
        y = (dialog.winfo_screenheight() // 2) - (740 // 2)
        dialog.geometry(f"1020x740+{x}+{y}")

        # 顶部标题条
        hdr = tk.Frame(dialog, bg=CLR_HEADER_BG, height=48)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"📷 照片管理", font=('Arial', 14, 'bold'),
                 bg=CLR_HEADER_BG, fg='white').pack(side=tk.LEFT, padx=16, pady=10)
        tk.Label(hdr, text=f"件号: {part_number}  |  架位: {location or '全部'}",
                 font=('Arial', 10), bg=CLR_HEADER_BG, fg='#93C5FD').pack(
                     side=tk.RIGHT, padx=16, pady=10)

        # 照片展示区（带滚动条）
        canvas_frame = tk.Frame(dialog, bg=CLR_BG)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        # 提示文字
        tk.Label(canvas_frame, text="💡 点击图片查看大图  |  点击 × 删除",
                 font=('Arial', 9), bg=CLR_BG, fg=CLR_SUBTEXT).pack(anchor='w', pady=(0, 6))

        wrapper = tk.Frame(canvas_frame, bg=CLR_BG)
        wrapper.pack(fill=tk.BOTH, expand=True)

        self._refresh_photo_view(wrapper, part_number, location, dialog)

        # 底部按钮
        btn_frame = tk.Frame(dialog, bg=CLR_CARD, height=52)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        btn_frame.pack_propagate(False)

        def do_upload():
            self._upload_photo(part_number, location)
            self._refresh_photo_view(wrapper, part_number, location, dialog)

        ttk.Button(btn_frame, text="📷 上传照片", command=do_upload).pack(
            side=tk.LEFT, padx=12, pady=10)
        ttk.Button(btn_frame, text="🔄 刷新", command=lambda: self._refresh_photo_view(
            wrapper, part_number, location, dialog)).pack(side=tk.LEFT, padx=4, pady=10)
        ttk.Button(btn_frame, text="✕ 关闭", command=dialog.destroy).pack(
            side=tk.RIGHT, padx=12, pady=10)

    def _refresh_photo_view(self, canvas_frame, part_number, location, dialog):
        """刷新照片展示区"""
        for widget in canvas_frame.winfo_children():
            widget.destroy()

        canvas = tk.Canvas(canvas_frame, bg=CLR_BG, highlightthickness=0)
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
            empty_frame = tk.Frame(canvas, bg=CLR_CARD, bd=1, relief=tk.GROOVE,
                                    width=400, height=120)
            empty_frame.pack(pady=40)
            empty_frame.pack_propagate(False)
            tk.Label(empty_frame, text="📷", font=('Arial', 32), bg=CLR_CARD,
                     fg=CLR_SUBTEXT).pack(pady=(20, 4))
            tk.Label(empty_frame, text="暂无照片，点击上方「上传照片」添加",
                     font=('Arial', 10), bg=CLR_CARD, fg=CLR_SUBTEXT).pack()
            canvas.create_window(200, 60, window=empty_frame)
            canvas.configure(scrollregion=(0, 0, 400, 150))
            return

        # 每行4张，更大缩略图
        THUMB_W = 220
        THUMB_H = 200
        COLS = 4
        PAD = 12

        total_rows = (len(photos) + COLS - 1) // COLS
        canvas_width  = COLS * (THUMB_W + PAD * 2)
        canvas_height = total_rows * (THUMB_H + 50 + PAD)
        canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))

        dialog._thumbs = {}

        for idx, photo in enumerate(photos):
            photo_id, file_path, file_name, desc, created = photo
            col = idx % COLS
            row = idx // COLS
            x = col * (THUMB_W + PAD * 2) + PAD
            y = row * (THUMB_H + 50 + PAD) + PAD

            # 卡片背景（圆角模拟）
            card = tk.Frame(canvas, bg=CLR_CARD, bd=1, relief=tk.GROOVE,
                            highlightthickness=1, highlightcolor=CLR_BORDER,
                            cursor='hand2')
            canvas.create_window(x, y, window=card, width=THUMB_W,
                                 height=THUMB_H + 40)

            # 缩略图（保持宽高比，居中）
            try:
                img = Image.open(file_path)
                # 计算等比缩放
                img_w, img_h = img.size
                scale = min((THUMB_W - 16) / img_w, (THUMB_H - 16) / img_h, 1)
                new_w, new_h = int(img_w * scale), int(img_h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                photo_img = ImageTk.PhotoImage(img)
                dialog._thumbs[photo_id] = photo_img
                # 用Frame居中显示图片
                img_container = tk.Frame(card, bg='#F8FAFC', width=THUMB_W-8, height=THUMB_H-8)
                img_container.pack(pady=4)
                img_container.pack_propagate(False)
                img_lbl = tk.Label(img_container, image=photo_img, bg='#F8FAFC', cursor='hand2')
                img_lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            except Exception:
                img_lbl = tk.Label(card, text="图片\n无法显示",
                                   bg='#F1F5F9', fg=CLR_SUBTEXT,
                                   font=('Arial', 10), width=22, height=9,
                                   cursor='hand2')
            img_lbl.pack(pady=(6, 2))
            img_lbl.bind('<Button-1>', lambda e, fp=file_path: self._view_full_photo(fp))

            # 文件名
            fname = (file_name or os.path.basename(file_path))[:20]
            tk.Label(card, text=fname, bg=CLR_CARD, fg=CLR_TEXT,
                     font=('Arial', 8), anchor='w').pack(
                         fill=tk.X, padx=6, pady=(0, 2))

            # 删除按钮
            def delete_photo(pid=photo_id, fp=file_path, cfd=canvas_frame, loc=location):
                if messagebox.askyesno("确认删除", "确定要删除这张照片吗？"):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
                    self.cursor.execute('DELETE FROM photos WHERE id=?', (pid,))
                    self.conn.commit()
                    self._refresh_photo_view(cfd, part_number, loc, dialog)

            tk.Button(card, text='🗑', command=delete_photo,
                     font=('Arial', 9), fg=CLR_DANGER, bg=CLR_CARD,
                     bd=0, cursor='hand2', width=4).pack(side=tk.BOTTOM, pady=2)

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
        """查看大图（正常窗口，ESC或点击关闭按钮）"""
        try:
            img = Image.open(file_path)
            win = tk.Toplevel(self.root)
            fname = os.path.basename(file_path)
            win.title(f"照片查看 - {fname}")

            # 限制最大尺寸，自适应屏幕
            max_w, max_h = 1200, 850
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            max_w = min(max_w, int(sw * 0.85))
            max_h = min(max_h, int(sh * 0.85))
            w, h = img.size
            ratio = min(max_w / w, max_h / h, 1)
            new_size = (int(w * ratio), int(h * ratio))

            img_large = img.resize(new_size, Image.LANCZOS)
            photo = ImageTk.PhotoImage(img_large)

            # 顶部栏：文件名 + 关闭按钮
            topbar = tk.Frame(win, bg='#1e293b', height=40)
            topbar.pack(fill=tk.X, side=tk.TOP)
            topbar.pack_propagate(False)

            tk.Label(topbar, text=f"  📷 {fname}", font=('Arial', 10),
                     bg='#1e293b', fg='#94A3B8', anchor='w').pack(
                         side=tk.LEFT, fill=tk.X, expand=True, pady=8)

            close_btn = tk.Button(topbar, text='✕ 关闭', font=('Arial', 9, 'bold'),
                                  bg='#dc2626', fg='white', bd=0, padx=16, pady=4,
                                  cursor='hand2', command=win.destroy)
            close_btn.pack(side=tk.RIGHT, pady=6, padx=8)

            # 图片区域（深色背景，点击也关闭）
            img_frame = tk.Frame(win, bg='#0f172a')
            img_frame.pack(fill=tk.BOTH, expand=True)

            img_lbl = tk.Label(img_frame, image=photo, bg='#0f172a', cursor='hand2')
            img_lbl.image = photo   # 防止GC
            img_lbl.pack(pady=20)

            # 绑定关闭事件
            def close_win(e=None):
                win.destroy()

            img_lbl.bind('<Button-1>', lambda e: close_win())
            win.bind('<Escape>', lambda e: close_win())
            close_btn.config(command=close_win)

            # 窗口居中
            win.update_idletasks()
            win_w = new_size[0] + 40
            win_h = new_size[1] + 80
            x = (sw - win_w) // 2
            y = (sh - win_h) // 2
            win.geometry(f"{win_w}x{win_h}+{x}+{y}")
            win.focus_set()
            win.grab_set()

        except Exception as e:
            messagebox.showerror("错误", f"无法显示图片: {str(e)}")

    # ==================== 关于对话框 ====================
    def show_about(self):
        """显示关于 / 操作说明"""
        dialog = tk.Toplevel(self.root)
        dialog.title("ℹ 关于")
        dialog.geometry("680x600")
        dialog.configure(bg=CLR_BG)
        dialog.grab_set()
        dialog.transient(self.root)

        # 标题
        hdr = tk.Frame(dialog, bg=CLR_HEADER_BG, height=54)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="ℹ  北京维护中心乘务航材管理 — 操作说明",
                  font=('Arial', 13, 'bold'), bg=CLR_HEADER_BG, fg=CLR_HEADER_FG).pack(pady=14)

        # 内容区（带滚动）
        canvas = tk.Canvas(dialog, bg=CLR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        content = tk.Frame(canvas, bg=CLR_BG, padx=24, pady=20)
        canvas.create_window((0, 0), window=content, anchor='nw', width=660)

        def _on_frame_config(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        content.bind('<Configure>', _on_frame_config)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), 'units')
        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        dialog.bind('<Destroy>', lambda e: canvas.unbind_all('<MouseWheel>'))

        def sec(title, body):
            """小节"""
            tk.Label(content, text=title, font=('Arial', 11, 'bold'),
                     bg=CLR_BG, fg=CLR_PRIMARY, anchor='w').pack(fill=tk.X, pady=(10, 2))
            tk.Frame(content, bg=CLR_PRIMARY, height=1).pack(fill=tk.X, pady=(0, 6))
            for line in body:
                tk.Label(content, text=line, font=('Arial', 9), bg=CLR_BG,
                         fg=CLR_TEXT, anchor='w', justify=tk.LEFT).pack(fill=tk.X, padx=8)

        sec("📌 基本信息", [
            "版本：v3.4   |   2026.06   |   作者：wu_fan1@hnair.com",
            "运行：双击「北京维护中心乘务航材管理_v3.4.exe」即可，无需安装 Python",
            f"数据库：程序同目录下 {os.path.basename(DB_PATH)}（SQLite，启动时自动创建）",
            "照片目录：程序同目录下 photos/ 文件夹",
        ])

        sec("🚀 快速开始", [
            "1. 首次运行：直接打开程序，数据库自动创建",
            "2. 导入 Excel：点击左上角「文件」菜单 → 「导入 Excel」",
        ])

        sec("📋 日常操作", [
            "➕ 新增航材：填写件号、描述、架位号等信息保存",
            "✏ 编辑航材：选中行 → 点击编辑 → 修改后保存",
            "📥 入库：选中航材 → 填写数量和操作员 → 自动生成件序号",
            "📤 出库：选中航材 → 选择个体件 → 填写领用人和用途",
            "📷 照片：点击主表格「📷 N」列，直接打开该件照片图库",
            "📋 出入库记录：主界面按钮区直接点击查看（支持筛选/导出）",
        ])

        sec("🔍 搜索与预警", [
            "搜索：在搜索框输入关键词（件号/描述/架位号），回车或点搜索",
            "",
            "【低库存预警】（测试中）",
            "  • 默认规则：未手动设置时，最低库存 = 总数量 × 20%（最低为1）",
            "  • 视觉标记：主表格中，低库存行显示红色背景",
            "  • 手动设置：新增/编辑航材时，可手动填写最低库存数值",
            "  • 关闭预警：将最低库存设为0即可",
            "  • 独立查询：菜单「查询」→「低库存预警」可查看所有低库存项及缺口",
            "",
            "【有效期预警】主表格「有效期提醒」列显示颜色标记",
            "  🟢 正常（>180天）  🟡 即将到期（90~180天）  🔴 到期（≤90天）",
        ])

        sec("📷 照片管理", [
            "上传：点击主表格照片列「📷 N」，或点击「📷 上传照片」",
            "查看：点击缩略图全屏查看，按 ESC 或点关闭按钮退出",
            "存储：照片保存在程序同目录 photos/ 文件夹",
        ])

        sec("📌 常见问题", [
            "Q：界面显示不全？→ 最大化窗口，或调整 Windows 显示缩放为100%",
            "Q：Windows 拦截程序？→ 点击「更多信息」→「仍要运行」",
        ])

        sec(f"💾 数据备份（{os.path.basename(DB_PATH)}）", [
            "备份是保护数据安全最重要的一环，建议每周备份一次。",
            "",
            "【方法一：直接复制（推荐）】",
            "  1. 关闭程序（确保数据库已保存）",
            "  2. 复制整个程序文件夹到备份位置（U盘、移动硬盘或网盘）",
            "  3. 关键文件：{db}（数据库）和 photos/（照片）".format(db=os.path.basename(DB_PATH)),
            "",
            "【方法二：仅备份数据文件】",
            "  1. 关闭程序",
            f"  2. 复制 {os.path.basename(DB_PATH)} 到安全位置",
            "  3. 复制 photos/ 整个文件夹到安全位置",
            "  4. 恢复时：将两个文件/文件夹放回程序同目录即可",
            "",
            "【方法三：导出 Excel 作为辅助备份】",
            "  1. 程序内点击「文件」→「导出 Excel」",
            "  2. 选择保存位置，生成 .xlsx 文件",
            "  3. 注意：Excel 不含照片数据和出入库记录，建议配合方法一/二使用",
        ])
        sec("📝 版本更新记录", [
            "v3.4  彻底删除个体件跟踪，只按数量管理库存；简化出库/入库/导入逻辑；新增低库存预警（测试中）",
            "v3.3  照片列支持点击直达图库；优化缩略图显示比例；修复全屏查看器关闭功能",
            "v3.2  主表格新增照片数量列；出入库记录入口调整至主界面；完善照片路径管理",
            "v3.1  优化界面布局，修复标题栏显示问题；新增出入库记录查询模块",
            "v3.0  系统重构：应用名称更新；新增照片管理功能；优化件号生成逻辑",
            "v2.0  数据库升级至 SQLite；新增件序号管理；新增库存预警功能；发布 Windows 打包版本",
            "v1.0  初始版本发布：实现航材基础信息管理功能",
            
        ])

        # 底部关闭按钮
        btn_frame = tk.Frame(dialog, bg=CLR_BG, height=50)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        btn_frame.pack_propagate(False)
        ttk.Button(btn_frame, text="✕ 关闭", command=dialog.destroy, width=16).pack(pady=10)

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

        # 有效期预警：当前版本 inventory 表中无 expiry_date 字段，跳过查询
        rows = []

        if not rows:
            ttk.Label(dialog, text="✅ 未来90天内没有到期航材（当前版本未启用有效期字段）", font=('Arial', 12)).pack(pady=30)
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

        # 有效期统计：当前版本 inventory 表中无 expiry_date 字段，设为 0
        expiry_count = 0

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

        ttk.Button(dialog, text="📋 详细出入库记录", command=self.show_transaction_log).pack(
            side=tk.LEFT, padx=(0, 10), pady=15)
        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=15)

    # ==================== 详细出入库记录 ====================
    def show_transaction_log(self):
        """详细出入库记录查询"""
        dialog = tk.Toplevel(self.root)
        dialog.title("📋 详细出入库记录")
        dialog.geometry("1100x680")
        dialog.configure(bg=CLR_BG)
        dialog.grab_set()
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (1100 // 2)
        y = (dialog.winfo_screenheight() // 2) - (680 // 2)
        dialog.geometry(f"1100x680+{x}+{y}")

        # 顶部标题
        hdr = tk.Frame(dialog, bg=CLR_HEADER_BG, height=48)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="📋 详细出入库记录", font=('Arial', 14, 'bold'),
                 bg=CLR_HEADER_BG, fg='white').pack(side=tk.LEFT, padx=16, pady=10)

        # 筛选栏
        filter_frame = tk.Frame(dialog, bg=CLR_CARD, bd=1, relief=tk.GROOVE)
        filter_frame.pack(fill=tk.X, padx=14, pady=(14, 0))

        tk.Label(filter_frame, text="类型:", font=('Arial', 10), bg=CLR_CARD).pack(side=tk.LEFT, padx=(12, 4), pady=10)
        type_var = tk.StringVar(value='全部')
        ttk.Combobox(filter_frame, textvariable=type_var, values=['全部', '入库', '出库'],
                     state='readonly', width=8, font=('Arial', 10)).pack(side=tk.LEFT, padx=(0, 12), pady=10)

        tk.Label(filter_frame, text="件号/描述:", font=('Arial', 10), bg=CLR_CARD).pack(side=tk.LEFT, padx=(0, 4), pady=10)
        search_var = tk.StringVar()
        search_ent = ttk.Entry(filter_frame, textvariable=search_var, width=16, font=('Arial', 10))
        search_ent.pack(side=tk.LEFT, padx=(0, 12), pady=10)

        tk.Label(filter_frame, text="近", font=('Arial', 10), bg=CLR_CARD).pack(side=tk.LEFT, padx=(0, 4), pady=10)
        days_var = tk.StringVar(value='30')
        days_combo = ttk.Combobox(filter_frame, textvariable=days_var,
                                   values=['7', '30', '90', '365', '全部'],
                                   state='readonly', width=6, font=('Arial', 10))
        days_combo.pack(side=tk.LEFT, padx=(0, 4), pady=10)
        tk.Label(filter_frame, text="天", font=('Arial', 10), bg=CLR_CARD).pack(side=tk.LEFT, padx=(0, 12), pady=10)

        def do_filter():
            self._refresh_log_tree(log_tree, type_var.get(), search_var.get(), days_var.get(), count_label)
        def export_log():
            self._export_transaction_log(type_var.get(), search_var.get(), days_var.get())

        ttk.Button(filter_frame, text="🔍 查询", command=do_filter).pack(side=tk.LEFT, padx=(0, 6), pady=10)
        ttk.Button(filter_frame, text="📥 导出Excel", command=export_log).pack(side=tk.LEFT, padx=(0, 6), pady=10)
        count_label = tk.Label(filter_frame, text="", font=('Arial', 10, 'bold'),
                                bg=CLR_CARD, fg=CLR_PRIMARY)
        count_label.pack(side=tk.LEFT, padx=(8, 0), pady=10)

        # 表格区
        table_frame = tk.Frame(dialog, bg=CLR_CARD, bd=1, relief=tk.GROOVE)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(10, 0))

        columns = ('日期时间', '类型', '件号', '描述', '架位', '数量', '经手人', '用途', '备注')
        log_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=22)

        col_widths = {'日期时间': 150, '类型': 65, '件号': 130, '描述': 160, '架位': 80,
                      '数量': 55, '经手人': 90, '用途': 120, '备注': 150}
        for col in columns:
            log_tree.heading(col, text=col,
                             command=lambda c=col: self._sort_log_tree(log_tree, c))
            log_tree.column(col, width=col_widths[col], anchor='center' if col != '备注' else 'w')

        # 入库/出库 tag 颜色
        log_tree.tag_configure('IN', background='#DCFCE7', foreground='#166534')
        log_tree.tag_configure('OUT', background='#FEE2E2', foreground='#991B1B')
        log_tree.tag_configure('oddrow', background=CLR_ROW_ODD)
        log_tree.tag_configure('evenrow', background=CLR_ROW_EVEN)

        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=log_tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=log_tree.xview)
        log_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 初始加载
        self._refresh_log_tree(log_tree, '全部', '', '30', count_label)

        # 回车查询
        search_ent.bind('<Return>', lambda e: do_filter())

        # 底部按钮
        btn_frame = tk.Frame(dialog, bg=CLR_CARD, height=48)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        btn_frame.pack_propagate(False)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT, padx=12, pady=8)

    def _sort_log_tree(self, tree, column):
        """点击表头排序"""
        data = [(tree.set(item, column), item) for item in tree.get_children('')]
        try:
            data.sort(key=lambda x: float(x[0]) if column == '数量' else x[0])
        except Exception:
            data.sort()
        for index, (val, item) in enumerate(data):
            tree.move(item, '', index)

    def _refresh_log_tree(self, tree, trans_type, search, days, count_label):
        """刷新出入库记录列表"""
        for item in tree.get_children():
            tree.delete(item)

        # 构建查询
        where = []
        params = []
        if trans_type != '全部':
            where.append("trans_type = ?")
            params.append('IN' if trans_type == '入库' else 'OUT')
        if search:
            where.append("(part_number LIKE ? OR description LIKE ? OR operator LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        if days != '全部':
            where.append(f"trans_date >= date('now', '-{days} days')")

        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

        self.cursor.execute(f'''
            SELECT trans_date, trans_type, part_number, description,
                   location, quantity, operator, purpose, remark
            FROM transactions
            {where_sql}
            ORDER BY trans_date DESC, id DESC
        ''', params)

        rows = self.cursor.fetchall()
        today = datetime.now()

        for idx, row in enumerate(rows):
            tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
            trans_type_disp = '✅ 入库' if row[1] == 'IN' else '📤 出库'
            tree.insert('', tk.END, tags=(row[1], tag), values=(
                row[0] or '',
                trans_type_disp,
                row[2] or '',
                row[3] or '',
                row[4] or '-',
                f"{row[5]:.0f}" if row[5] is not None else '',
                row[6] or '',
                row[7] or '',
                row[8] or ''
            ))

        total_in = sum(r[5] for r in rows if r[1] == 'IN' and r[5])
        total_out = sum(r[5] for r in rows if r[1] == 'OUT' and r[5])
        count_label.config(text=f"共 {len(rows)} 条 | 入库 {total_in:.0f} 件 | 出库 {total_out:.0f} 件")

    def _export_transaction_log(self, trans_type, search, days):
        """导出出入库记录到Excel"""
        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(
            title="导出出入库记录",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx")],
            initialfile=f"出入库记录_{datetime.now().strftime('%Y%m%d')}")
        if not file_path:
            return

        where = []
        params = []
        if trans_type != '全部':
            where.append("trans_type = ?")
            params.append('IN' if trans_type == '入库' else 'OUT')
        if search:
            where.append("(part_number LIKE ? OR description LIKE ? OR operator LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        if days != '全部':
            where.append(f"trans_date >= date('now', '-{days} days')")

        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

        self.cursor.execute(f'''
            SELECT trans_date as 日期时间,
                   CASE trans_type WHEN 'IN' THEN '入库' ELSE '出库' END as 类型,
                   part_number as 件号, description as 描述,
                   location as 架位, quantity as 数量,
                   operator as 经手人, purpose as 用途, remark as 备注
            FROM transactions
            {where_sql}
            ORDER BY trans_date DESC, id DESC
        ''', params)
        rows = self.cursor.fetchall()

        if not rows:
            messagebox.showwarning("提示", "当前筛选条件下无记录")
            return

        import pandas as pd
        df = pd.DataFrame(rows, columns=['日期时间', '类型', '件号', '描述', '架位', '数量', '经手人', '用途', '备注'])
        try:
            df.to_excel(file_path, index=False, engine='openpyxl')
            messagebox.showinfo("成功", f"已导出 {len(rows)} 条记录到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

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

                # 每次 Excel 行都插入一条独立记录（不再合并）
                self.cursor.execute('''
                INSERT OR IGNORE INTO inventory (part_number, description, total_quantity, unit,
                                       location, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (part_number, description, qty, unit or '个', location or None,
                     remark, now, now))
                imported += 1

            self.conn.commit()

            message = (f"导入完成！\n"
                      f"✅ 新增记录: {imported} 条\n"
                      f"🔄 跳过（数量为0）: {skipped} 条\n"
                      f"📋 含N/A航材: {na_items} 条\n"
                      f"💡 每行Excel独立导入，可重复件号+架位")
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
