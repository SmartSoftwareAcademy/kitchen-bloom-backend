# Jazzmin Settings
JAZZMIN_SETTINGS = {
    # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_title": "Kitchen Bloom Admin",
    # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_header": "Kitchen Bloom",
    # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_brand": "Kitchen Bloom",
    # Welcome text on the login screen
    "welcome_sign": "Welcome to Kitchen Bloom Admin",
    # Copyright on the footer
    "copyright": "Kitchen Bloom Ltd",
    
    # Logo to use for your site, must be present in static files, used for brand on top left
    "site_logo": "/logo/logo.png",

    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle img-fluid w-50 custom-logo-size",

    # Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
    "site_icon": "/logo/logo.png",

    # The model admin to search from the search bar, search bar omitted if excluded
    "search_model": "accounts.User",
    # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
    "user_avatar": None,
    # Links to put along the top menu
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        # external url that opens in a new window (Permissions can be added)
        {"name": "Support", "url": "https://github.com/farridav/django-jazzmin/issues", "new_window": True},
        # model admin to link to (Permissions checked against model)
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
            "icon": "fas fa-comments",
            "permissions": ["inventory.view_inventorytransaction"]
        }]
    },
    # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
    # for the full list of 5.13.0 free icon classes
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.User": "fas fa-user-tie",
        "accounts.Role": "fas fa-user-tag",
        "inventory": "fas fa-box",
    },
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
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
}
