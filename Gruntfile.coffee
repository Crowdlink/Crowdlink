module.exports = (grunt) ->

  # Project configuration.
  grunt.initConfig

    # Metadata.
    pkg: grunt.file.readJSON("package.json")
    banner: "/*! <%= pkg.title || pkg.name %> - v<%= pkg.version %> - " + "<%= grunt.template.today(\"yyyy-mm-dd\") %>\n" + "<%= pkg.homepage ? \"* \" + pkg.homepage + \"\\n\" : \"\" %>" + "* Copyright (c) <%= grunt.template.today(\"yyyy\") %> <%= pkg.author.name %>;" + " Licensed <%= _.pluck(pkg.licenses, \"type\").join(\", \") %> */\n"

    haml:
      development:
        options:
          loadPath: ["haml"]
        files:
          "templates/signup.html": "haml/signup.haml"
          "templates/project.html": "haml/project.haml"
          "templates/home.html": "haml/home.haml"
          "templates/login.html": "haml/login.haml"
          "templates/issue.html": "haml/issue.haml"
          "templates/profile.html": "haml/profile.haml"
          "templates/account.html": "haml/account.haml"
          "templates/403.html": "haml/403.haml"
          "templates/new_issue.html": "haml/new_issue.haml"
          "templates/new_project.html": "haml/new_project.haml"
          "templates/new_solution.html": "haml/new_solution.haml"
          "templates/user_home.html": "haml/user_home.haml"
          "templates/base.html": "haml/base.haml"
          "templates/psettings.html": "haml/psettings.haml"
          "templates/events/issue.html": "haml/events/issue.haml"
          "templates/events/comment.html": "haml/events/comment.haml"
          "templates/events/fallback.html": "haml/events/fallback.haml"

    coffee:
      compile:
        files:
          "static/js/app.js": "coffee/app.coffee"
          "static/js/controllers.js": "coffee/controllers.coffee"
          "static/js/services.js": "coffee/services.coffee"
          "static/js/lib.js": "coffee/lib.coffee"

    compass:
      development:
        options:
          sassDir: ["scss"]
          cssDir: ["static/css"]

    less:
      development:
        options:
          paths: ["less"]
        files:
          "static/lib/css/bootstrap.min.css": "less/bootstrap/bootstrap.less"

      production:
        options:
          paths: ["less"]
          cleancss: true
        files:
          "static/lib/css/bootstrap.min.css": "less/bootstrap/bootstrap.less"

    shell:
      reload:
        command: 'uwsgi --stop uwsgi.pid; sleep 1.5; uwsgi --ini uwsgi.ini'

    watch:
      bootstrap:
        files: ['**/*.less']
        tasks: ['less:development']
      haml:
        files: ['**/*.haml']
        tasks: ['haml']
      compass:
        files: ['**/*.scss']
        tasks: ['compass']
      dev_server:
        files: ['**/*.py', '**/*.cfg']
        tasks: ['shell:reload']
      coffee:
        files: ['coffee/**/*.coffee']
        tasks: ['coffee:compile']

  grunt.loadNpmTasks('grunt-contrib-less')
  grunt.loadNpmTasks('grunt-contrib-watch')
  grunt.loadNpmTasks('grunt-contrib-haml')
  grunt.loadNpmTasks('grunt-contrib-jshint')
  grunt.loadNpmTasks('grunt-contrib-compass')
  grunt.loadNpmTasks('grunt-contrib-coffee')
  grunt.loadNpmTasks('grunt-shell')

  grunt.registerTask "default", ["less", "haml", "compass", "coffee"]
