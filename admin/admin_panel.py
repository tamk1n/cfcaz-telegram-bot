#!/usr/bin/env python3
"""
Simple Flask Admin Panel for Managing Live Match Links
Run with: python3 admin_panel.py
Access at: http://localhost:5000
"""

import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime
from supabase import create_client


# Add parent directory to Python path to import from bot module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import settings
from utils import get_supabase_client

from dotenv import load_dotenv

load_dotenv()

template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.getenv('ADMIN_SECRET_KEY')

ADMIN_USERNAME = settings.ADMIN_USERNAME
ADMIN_PASSWORD = settings.ADMIN_PASSWORD

def connect_supabase():
    """Connect to Supabase (placeholder function)"""
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY
    supabase_client = create_client(url, key)

    return supabase_client

def load_match_links(link_id=None):
    """Load matches from db"""
    try:
        supabase_client = connect_supabase()
        if link_id:
            response = (supabase_client.table("Matches").select("*").eq("id", link_id).execute())
        else:
            response = (supabase_client.table("Matches").select("*").execute())
        print(response)
        return response.data
    except Exception as e:
        print(f"Error loading match links: {e}")
        return []

def create_match_link(link):
    """Save match link to db"""
    try:
        supabase_client = connect_supabase()
        supabase_client.table("Matches").insert(link).execute()
    except Exception as e:
        print(f"Error saving match link: {e}")
        return

def update_match_link(link):
    """Update match link in db"""
    try:
        supabase_client = connect_supabase()
        supabase_client.table("Matches").update(link).eq("id", link["id"]).execute()
    except Exception as e:
        print(f"Error updating match link: {e}")
        return

def delete_match_link(link_id):
    """Delete match link from db"""
    try:
        supabase_client = connect_supabase()
        supabase_client.table("Matches").delete().eq("id", link_id).execute()
    except Exception as e:
        print(f"Error deleting match link: {e}")
        return
def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('Uğurla daxil oldunuz!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Yanlış istifadəçi adı və ya şifrə!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.pop('logged_in', None)
    flash('Çıxış etdiniz!', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Main admin page - list all match links"""
    links = load_match_links()
    return render_template('index.html', links=links)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_link():
    """Add new match link"""
    if request.method == 'POST':
        match_title = request.form.get('match_title')
        match_hour = request.form.get('match_hour', '00')
        match_minute = request.form.get('match_minute', '00')
        match_time = f"{match_hour.zfill(2)}:{match_minute.zfill(2)}"
        language = request.form.get('language', 'az')
        stream_url = request.form.get('stream_url')
        is_active = request.form.get('is_active') == 'on'
        
        if match_title and stream_url:
            new_link = {
                'match_title': match_title,
                'match_time': match_time,
                'language': language,
                'stream_url': stream_url,
                'is_active': is_active,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            create_match_link(new_link)
            flash('Oyun linki əlavə edildi!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Zəhmət olmasa bütün məlumatları doldurun!', 'error')
    
    return render_template('add_link.html')

@app.route('/edit/<int:link_id>', methods=['GET', 'POST'])
@login_required
def edit_link(link_id):
    """Edit existing match link"""
    link = load_match_links(link_id)[0]
    print(link)
    if not link:
        flash('Link tapılmadı!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        link['match_title'] = request.form.get('match_title')
        match_hour = request.form.get('match_hour', '00')
        match_minute = request.form.get('match_minute', '00')
        link['match_time'] = f"{match_hour.zfill(2)}:{match_minute.zfill(2)}"
        link['stream_url'] = request.form.get('stream_url')
        link['language'] = request.form.get('language')
        link['is_active'] = request.form.get('is_active') == 'on'

        update_match_link(link)
        flash('Link yeniləndi!', 'success')
        return redirect(url_for('index'))
    
    return render_template('edit_link.html', link=link)

@app.route('/delete/<int:link_id>')
@login_required
def delete_link(link_id):
    """Delete match link"""
    link = load_match_links(link_id)[0]
    if not link:
        flash('Link tapılmadı!', 'error')
    else:
        delete_match_link(link_id)
        flash('Link silindi!', 'success')
    return redirect(url_for('index'))

@app.route('/toggle/<int:link_id>')
@login_required
def toggle_active(link_id):
    """Toggle active status of a link"""
    link = load_match_links(link_id)[0]

    if link:
        link['is_active'] = not link.get('is_active', False)
        update_match_link(link)
        status = 'aktiv' if link['is_active'] else 'deaktiv'
        flash(f'Link {status} edildi!', 'success')
    
    return redirect(url_for('index'))

@app.route('/logs')
@login_required
def view_logs():
    """View bot logs"""
    log_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'bot.log')
    
    # Get number of lines to display (default 100, max 1000)
    num_lines = request.args.get('lines', 100, type=int)
    if num_lines > 1000:
        num_lines = 1000
    
    # Get filter level (all, info, warning, error)
    filter_level = request.args.get('level', 'all')
    
    logs = []
    try:
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                
                # Get last N lines
                recent_lines = all_lines[-num_lines:] if len(all_lines) > num_lines else all_lines
                
                # Filter by level if specified
                for line in reversed(recent_lines):  # Show newest first
                    if filter_level == 'all':
                        logs.append(line.strip())
                    elif filter_level.upper() in line:
                        logs.append(line.strip())
        else:
            flash('Log faylı tapılmadı!', 'warning')
    except Exception as e:
        flash(f'Log oxunarkən xəta: {e}', 'error')
    
    return render_template('logs.html', logs=logs, num_lines=num_lines, filter_level=filter_level)

@app.route('/statistics')
@login_required
def view_statistics():
    supabase_client = get_supabase_client()
    
    # Get all users
    response = supabase_client.table("Users").select("*").execute()
    users = response.data
    
    # Sort by last_active (most recent first)
    users = sorted(
        [u for u in users if u.get('last_active')],
        key=lambda x: x['last_active'],
        reverse=True
    )
    
    stats = {
        'total_users': len(users),
        'users': users
    }
    
    return render_template('statistics.html', stats=stats)

if __name__ == '__main__':
    # Get port from environment variable (for Render deployment) or default to 5000
    port = int(os.getenv('PORT', 5000))
    
    print("=" * 50)
    print("Admin Panel başladıldı!")
    print(f"URL: http://localhost:{port}")
    
    app.run(debug=True, host='0.0.0.0', port=port)
