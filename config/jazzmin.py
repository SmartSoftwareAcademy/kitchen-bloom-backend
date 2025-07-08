# Jazzmin Settings
JAZZMIN_SETTINGS = {
    # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_title": "Nevada Pub & Restaurant",
    # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_header": "Nevada Pub & Restaurant",
    # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_brand": "Nevada Pub & Restaurant",
    # Welcome text on the login screen
    "welcome_sign": "Welcome to Nevada Pub & Restaurant",
    # Copyright on the footer
    "copyright": "Nevada Pub & Restaurant Ltd",
    
    # Logo to use for your site, must be present in static files, used for brand on top left
    "site_logo": "/logo/logo.png",

    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-fluid custom-logo-size",

    # Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
    "site_icon": "/logo/logo.png",

    # The model admin to search from the search bar, search bar omitted if excluded
    "search_model": "accounts.User",
    # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
    "user_avatar": None,
    
    # Links to put along the top menu
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"model": "auth.User"},
        {"app": "branches"},
        {"app": "inventory"},
        {"app": "sales"},
        {"app": "tables"},
        {"app": "crm"},
        {"app": "employees"},
        {"app": "payroll"},
    ],

    #############
    # User Menu #
    #############

    # Additional links to include in the user menu on the top right ("app" url type is not allowed)
    "usermenu_links": [
        {"name": "Support", "url": "https://codevertexitsolutions.com/", "new_window": True},
        {"model": "accounts.User"}
    ],

    #############
    # Side Menu #
    #############

    # Whether to display the side menu
    "show_sidebar": True,

    # Whether to aut expand the menu
    "navigation_expanded": False,

    # Hide these apps when generating side menu e.g (auth)
    "hide_apps": [],

    # Hide these models when generating side menu (e.g authman.CustomUser)
    "hide_models": [],

    # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
    "order_with_respect_to": ["authmanagement", "auth.group"],

    # Custom links to append to app groups, keyed on app name
    "custom_links": {
        "inventory": [{
            "name": "Inventory",
            "url": "inventory:inventory_transaction_list",
            "icon": "fas fa-boxes",
            "permissions": ["inventory.view_inventorytransaction"]
        }]
    },
    
    # Custom icons for side menu apps/models - Modern FontAwesome 6 icons
    "icons": {
        "auth": "fas fa-shield-halved",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.User": "fas fa-user-tie",
        "accounts": "fas fa-user-tag",
        "accounts": "fas fa-user-tag",
        "base.Branch": "fas fa-building",
        "base.BranchType": "fas fa-building",
        "base.BranchType": "fas fa-building",
        "inventory": "fas fa-boxes-stacked",
        "sales": "fas fa-cart-shopping",
        "tables": "fas fa-table",
        "crm": "fas fa-handshake",
        "employees": "fas fa-users-gear",
        "payroll": "fas fa-money-bill-transfer",
        "branches": "fas fa-building",
        "accounting": "fas fa-calculator",
        "kds": "fas fa-utensils",
        "loyalty": "fas fa-gift",
        "reporting": "fas fa-chart-line",
    },
    
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-right",
    "default_icon_children": "fas fa-circle",
    # UI Tweaks
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "show_ui_builder": True,
    "changeform_format": "horizontal_tabs",
    
    # override change forms on a per modeladmin basis
    "changeform_format_overrides": {"auth.user": "collapsible", "auth.group": "vertical_tabs"},
    
    # Add a language dropdown into the admin
    "language_chooser": True,
    
    # Modern UI Customizations
    "show_fullsidebar": True,
    "show_ui_builder": True,
    "navigation_expanded": False,
    "hide_apps": [],
    "hide_models": [],
    
    # Custom CSS for modern styling
    "custom_css": """
        <style>
            :root {
                --primary-color: #6366f1;
                --secondary-color: #8b5cf6;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --danger-color: #ef4444;
                --info-color: #06b6d4;
                --light-color: #f8fafc;
                --dark-color: #1e293b;
            }
            
            .navbar-brand {
                font-weight: 700;
                font-size: 1.5rem;
                color: var(--primary-color) !important;
            }
            
            .sidebar-dark-primary {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            }
            
            .sidebar-dark-primary .nav-sidebar > .nav-item > .nav-link {
                color: rgba(255, 255, 255, 0.9);
                border-radius: 8px;
                margin: 2px 8px;
                transition: all 0.3s ease;
            }
            
            .sidebar-dark-primary .nav-sidebar > .nav-item > .nav-link:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                transform: translateX(4px);
            }
            
            .sidebar-dark-primary .nav-sidebar > .nav-item > .nav-link.active {
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }
            
            .main-header {
                background: white;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                border-bottom: 1px solid #e2e8f0;
            }
            
            .content-wrapper {
                background-color: #f8fafc;
            }
            
            .card {
                border: none;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                transition: all 0.3s ease;
            }
            
            .card:hover {
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
                transform: translateY(-2px);
            }
            
            .card-header {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                color: white;
                border-radius: 12px 12px 0 0 !important;
                border: none;
                font-weight: 600;
            }
            
            .btn-primary {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            
            .btn-primary:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
            }
            
            .table {
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            }
            
            .table thead th {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                color: white;
                border: none;
                font-weight: 600;
                padding: 15px;
            }
            
            .table tbody tr:hover {
                background-color: rgba(99, 102, 241, 0.05);
            }
            
            .form-control {
                border-radius: 8px;
                border: 2px solid #e2e8f0;
                padding: 12px 16px;
                transition: all 0.3s ease;
            }
            
            .form-control:focus {
                border-color: var(--primary-color);
                box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
            }
            
            .alert {
                border-radius: 8px;
                border: none;
                padding: 16px 20px;
            }
            
            .alert-success {
                background: linear-gradient(135deg, var(--success-color) 0%, #34d399 100%);
                color: white;
            }
            
            .alert-warning {
                background: linear-gradient(135deg, var(--warning-color) 0%, #fbbf24 100%);
                color: white;
            }
            
            .alert-danger {
                background: linear-gradient(135deg, var(--danger-color) 0%, #f87171 100%);
                color: white;
            }
            
            .alert-info {
                background: linear-gradient(135deg, var(--info-color) 0%, #22d3ee 100%);
                color: white;
            }
            
            .pagination .page-link {
                border-radius: 8px;
                margin: 0 2px;
                border: none;
                color: var(--primary-color);
                transition: all 0.3s ease;
            }
            
            .pagination .page-link:hover {
                background-color: var(--primary-color);
                color: white;
                transform: translateY(-1px);
            }
            
            .pagination .page-item.active .page-link {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                border: none;
            }
            
            .custom-logo-size {
                max-height: 40px;
                width: auto;
            }
            
            .nav-sidebar .nav-link p {
                font-weight: 500;
            }
            
            .nav-sidebar .nav-link i {
                width: 20px;
                text-align: center;
                margin-right: 10px;
            }
        </style>
    """,
    
    # Custom JavaScript for enhanced interactions
    "custom_js": """
        <script>
            // Add smooth scrolling to all links
            document.addEventListener('DOMContentLoaded', function() {
                // Add loading animation to buttons
                const buttons = document.querySelectorAll('.btn');
                buttons.forEach(button => {
                    button.addEventListener('click', function() {
                        if (!this.classList.contains('btn-secondary')) {
                            this.style.transform = 'scale(0.95)';
                            setTimeout(() => {
                                this.style.transform = '';
                            }, 150);
                        }
                    });
                });
                
                // Add hover effects to cards
                const cards = document.querySelectorAll('.card');
                cards.forEach(card => {
                    card.addEventListener('mouseenter', function() {
                        this.style.transform = 'translateY(-4px)';
                    });
                    
                    card.addEventListener('mouseleave', function() {
                        this.style.transform = 'translateY(0)';
                    });
                });
                
                // Smooth sidebar navigation
                const navLinks = document.querySelectorAll('.nav-sidebar .nav-link');
                navLinks.forEach(link => {
                    link.addEventListener('click', function() {
                        navLinks.forEach(l => l.classList.remove('active'));
                        this.classList.add('active');
                    });
                });
            });
        </script>
    """,
}

# Jazzmin UI Customizer
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": True,
    "brand_small_text": False,
    "brand_colour": "navbar-cyan",
    "accent": "accent-orange",
    "navbar": "navbar-cyan",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": True,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-navy",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "simplex",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },
    "actions_sticky_top": True
}