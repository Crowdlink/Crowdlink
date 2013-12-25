module.exports = (grunt) ->

  # Project configuration.
  grunt.initConfig

    # Metadata.
    pkg: grunt.file.readJSON("package.json")
    banner: "/*! <%= pkg.title || pkg.name %> - v<%= pkg.version %> - " + "<%= grunt.template.today(\"yyyy-mm-dd\") %>\n" + "<%= pkg.homepage ? \"* \" + pkg.homepage + \"\\n\" : \"\" %>" + "* Copyright (c) <%= grunt.template.today(\"yyyy\") %> <%= pkg.author.name %>;" + " Licensed <%= _.pluck(pkg.licenses, \"type\").join(\", \") %> */\n"

    uglify:
      all:
        options:
          mangle: false
          sourceMap: 'static/js/common.map.js'
          sourceMappingURL: '/static/js/common.map.js'
          sourceMapPrefix: 2
        files:
          'static/js/common.min.js': ['static/js/app.js',
                                      'static/js/controllers.js',
                                      'static/js/services.js',
                                      'bower_components/noty/js/noty/jquery.noty.js',
                                      'static/js/noty_theme.js',
                                      'static/js/noty_topcenter.js']

    cssmin:
      all:
        files:
          'static/css/common.min.css': ['static/css/bootstrap.css',
                                        'static/css/main.css']

    coffeelint:
      app: ['processed/coffee/*.coffee']

    haml:
      development:
        options:
          loadPath: ["haml"]
        files:
          "templates/signup.html": "processed/haml/signup.haml"
          "templates/project.html": "processed/haml/project.haml"
          "templates/home.html": "processed/haml/home.haml"
          "templates/login.html": "processed/haml/login.haml"
          "templates/issue.html": "processed/haml/issue.haml"
          "templates/solution.html": "processed/haml/solution.haml"
          "templates/profile.html": "processed/haml/profile.haml"
          "templates/account.html": "processed/haml/account.haml"
          "templates/account/charges.html": "processed/haml/account/charges.haml"
          "templates/account/general.html": "processed/haml/account/general.haml"
          "templates/account/add_credit.html": "processed/haml/account/add_credit.haml"
          "templates/error.html": "processed/haml/error.haml"
          "templates/new_issue.html": "processed/haml/new_issue.haml"
          "templates/new_project.html": "processed/haml/new_project.haml"
          "templates/new_solution.html": "processed/haml/new_solution.haml"
          "templates/user_home.html": "processed/haml/user_home.haml"
          "templates/base.html": "processed/haml/base.haml"
          "templates/psettings.html": "processed/haml/psettings.haml"
          "templates/events/issue.html": "processed/haml/events/issue.haml"
          "templates/events/comment.html": "processed/haml/events/comment.haml"
          "templates/events/fallback.html": "processed/haml/events/fallback.haml"
          "templates/tos.html": "processed/haml/tos.haml"

    coffee:
      compile:
        files:
          "static/js/app.js": "processed/coffee/app.coffee"
          "static/js/controllers.js": "processed/coffee/controllers.coffee"
          "static/js/services.js": "processed/coffee/services.coffee"
          "static/js/noty_theme.js": "processed/coffee/noty_theme.coffee"
          "static/js/noty_topcenter.js": "processed/coffee/noty_topcenter.coffee"

    compass:
      development:
        options:
          sassDir: ["processed/scss"]
          cssDir: ["static/css"]

    less:
      development:
        options:
          paths: ["less"]
        files:
          "static/css/bootstrap.css": "processed/less/bootstrap/bootstrap.less"

      production:
        options:
          paths: ["less"]
          cleancss: true
        files:
          "static/lib/css/bootstrap.min.css": "less/bootstrap/bootstrap.less"

    shell:
      reload:
        command: 'uwsgi --stop uwsgi.pid; sleep 1.5; uwsgi --ini uwsgi.ini'
        options:
          stdout: true
          stderr: true
      clean:
        command: 'find . -name "*.pyc" -delete; find . -name "*.swo" -delete; find . -name "*.swp" -delete; echo "" > uwsgi.log'
      flake8:
        command: 'flake8 ./'
        options:
          stdout: true
          stderr: true
      new_flake8:
        command: 'git diff HEAD -U0 | flake8 --diff'
        options:
          stdout: true
          stderr: true
      jshint:
        command: 'coffee-jshint coffee/*.coffee'
        options:
          stdout: true
          stderr: true
      test:
        command: 'nosetests crowdlink.tests.api_tests crowdlink.tests.model_tests crowdlink.tests.event_tests --with-cover --cover-package=crowdlink -v'
        options:
          stdout: true
          stderr: true
      testall:
        command: 'nosetests --with-cover --cover-package=crowdlink --cover-html -v'
        options:
          stdout: true
          stderr: true
      proc_coffee:
        command: './util/preprocess.py coffee coffee -v'
        options:
          stdout: true
          stderr: true
      proc_haml:
        command: './util/preprocess.py haml haml -v'
        options:
          stdout: true
          stderr: true
      proc_less:
        command: './util/preprocess.py less less -v'
        options:
          stdout: true
          stderr: true
      proc_sass:
        command: './util/preprocess.py scss scss -v'
        options:
          stdout: true
          stderr: true

    inlinecss:
      main:
        options:
          removeStyleTags: false
        files:
          'assets/emailout/base.html': 'assets/email/base.html'

    watch:
      options:
        livereload: true
      bootstrap:
        files: ['**/*.less']
        tasks: ['shell:proc_less', 'less:development']
      haml:
        files: ['**/*.haml']
        tasks: ['shell:proc_haml', 'haml']
      compass:
        files: ['**/*.scss']
        tasks: ['shell:proc_sass', 'compass']
      dev_server:
        files: ['**/*.py', '/*.json']
        tasks: ['shell:reload']
      coffee:
        files: ['coffee/**/*.coffee']
        tasks: ['shell:proc_coffee', 'coffee:compile']
      email:
        files: ['assets/email/**/*.html']
        tasks: ['inlinecss:main']

  grunt.loadNpmTasks('grunt-contrib-less')
  grunt.loadNpmTasks('grunt-contrib-watch')
  grunt.loadNpmTasks('grunt-contrib-haml')
  grunt.loadNpmTasks('grunt-contrib-jshint')
  grunt.loadNpmTasks('grunt-contrib-compass')
  grunt.loadNpmTasks('grunt-contrib-coffee')
  grunt.loadNpmTasks('grunt-shell')
  grunt.loadNpmTasks('grunt-coffeelint')
  grunt.loadNpmTasks('grunt-contrib-uglify')
  grunt.loadNpmTasks('grunt-contrib-cssmin')
  grunt.loadNpmTasks('grunt-inline-css')

  grunt.registerTask "dev", ["shell:proc_coffee", "shell:proc_less",
                             "shell:proc_haml", "shell:proc_sass",
                             "less", "haml", "compass", "coffee"]
  grunt.registerTask "prod", ["shell:proc_coffee", "shell:proc_less",
                             "shell:proc_haml", "shell:proc_sass",
                             "less", "haml", "compass", "coffee",
                             "cssmin:all", "uglify:all"]
  grunt.registerTask "lint", ["shell:flake8", "coffeelint"]
  grunt.registerTask "flake8", ["shell:flake8"]
  grunt.registerTask "test", ["shell:test"]
  grunt.registerTask "testall", ["shell:testall"]
  grunt.registerTask "clean", ["shell:clean"]
  grunt.registerTask "new_flake8", ["shell:new_flake8"]
