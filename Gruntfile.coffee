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
                                      'static/js/miu.js',
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
          # Client side templates
          "static/templates/home.html": "processed/haml/home.haml"
          "static/templates/error.html": "processed/haml/error.haml"
          "static/templates/tos.html": "processed/haml/tos.haml"
          "static/templates/privacy.html": "processed/haml/privacy.haml"
          # Modals
          "static/templates/help_modal.html": "processed/haml/help_modal.haml"

          # Server Side
          "templates/base.html": "processed/haml/base.haml"
          "processed/email/base.html": "haml/email/base.haml"

    coffee:
      default:
        files:
          "static/js/app.js": "processed/coffee/app.coffee"
          "static/js/controllers.js": "processed/coffee/controllers.coffee"
          "static/js/services.js": "processed/coffee/services.coffee"
          "static/js/noty_theme.js": "processed/coffee/noty_theme.coffee"
          "static/js/noty_topcenter.js": "processed/coffee/noty_topcenter.coffee"
          "static/js/miu.js": "processed/coffee/miu.coffee"

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
      options:
        stdout: true
        stderr: true
      reload:
        command: 'uwsgi --stop uwsgi.pid; sleep 1.5; uwsgi --ini uwsgi.ini'
      clean:
        command: 'find . -name "*.pyc" -delete; find . -name "*.swo" -delete; find . -name "*.swp" -delete; echo "" > uwsgi.log'
      flake8:
        command: 'flake8 ./'
      new_flake8:
        command: 'git diff HEAD -U0 | flake8 --diff'
      jshint:
        command: 'coffee-jshint coffee/*.coffee'
      test:
        command: 'nosetests crowdlink.tests.json_api_tests crowdlink.tests.internal_api_tests crowdlink.tests.event_tests crowdlink.tests.json_api_unit_tests crowdlink.tests.acl_tests --with-cover --cover-package=crowdlink --cover-html -v'
      testall:
        command: 'nosetests --with-cover --cover-package=crowdlink --cover-html -v'
      proc_coffee:
        command: './util/preprocess.py coffee coffee -v'
      proc_haml:
        command: './util/preprocess.py haml haml -v'
      proc_less:
        command: './util/preprocess.py less less -v'
      proc_sass:
        command: './util/preprocess.py scss scss -v'
      compile_yaml:
        command: 'yaml2json ./assets/help/faq.yaml > ./static/faq.json'

    inlinecss:
      main:
        options:
          removeStyleTags: false
        files:
          'templates/email/base.html': 'processed/email/base.html'

    watch:
      less_pre:
        files: ['less/**/*.less']
        tasks: ['shell:proc_less']
      less:
        files: ['processed/less/**/*.less']
        tasks: ['less:development']
      haml_pre:
        files: ['haml/**/*.haml']
        tasks: ['shell:proc_haml']
      haml:
        files: ['processed/haml/**/*.haml']
        tasks: ['newer:haml']
      compass_pre:
        files: ['scss/**/*.scss']
        tasks: ['shell:proc_sass']
      compass:
        files: ['processed/scss/**/*.scss']
        tasks: ['compass']
      dev_server:
        files: ['**/*.py', '*.ini', '*.json']
        tasks: ['shell:reload']
      coffee_pre:
        files: ['coffee/**/*.coffee']
        tasks: ['shell:proc_coffee']
      coffee:
        files: ['processed/coffee/**/*.coffee']
        tasks: ['newer:coffee']
      email:
        files: ['processed/email/*.html']
        tasks: ['inlinecss:main']
      yaml:
        files: ['assets/help/*.yaml']
        tasks: ['shell:compile_yaml']
      static:
        files: ['static/**/*.css', 'static/**/*.html', 'static/**/*.js']
        options:
          livereload: true

  grunt.loadNpmTasks('grunt-contrib-less')    # compiled bootstrap
  grunt.loadNpmTasks('grunt-contrib-watch')   # watches for changes
  grunt.loadNpmTasks('grunt-contrib-haml')    # compiles our haml
  grunt.loadNpmTasks('grunt-contrib-compass') # compiles our compass
  grunt.loadNpmTasks('grunt-contrib-coffee')  # compiles our js
  grunt.loadNpmTasks('grunt-shell')           # runs utility commands
  grunt.loadNpmTasks('grunt-coffeelint')      # lints our coffeescript
  grunt.loadNpmTasks('grunt-contrib-uglify')  # combines js files and minifies
  grunt.loadNpmTasks('grunt-contrib-cssmin')  # minifies css files
  grunt.loadNpmTasks('grunt-inline-css')      # used for inlining email temps
  grunt.loadNpmTasks('grunt-newer')           # only compiles newer files

  grunt.registerTask "dev", ["shell:proc_coffee", "shell:proc_less",
                             "shell:proc_haml", "shell:proc_sass",
                             "less", "haml", "compass", "coffee",
                             "inlinecss:main","shell:compile_yaml"]
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
