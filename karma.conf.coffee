module.exports = (config) ->
  config.set
    files: ["static/lib/js/angular.min.js",
            "static/lib/js/jquery.min.js",
            "static/lib/js/**/*.js",
            "static/js/**/*.js",
            "jstest/lib/angular/angular-mocks.js",
            "jstest/unit/**/*.coffee"]

    autoWatch: true
    frameworks: ["jasmine"]
    browsers: ["Chrome"]
    plugins: ["karma-junit-reporter",
              "karma-chrome-launcher",
              "karma-firefox-launcher",
              "karma-coffee-preprocessor",
              "karma-jasmine"]

    junitReporter:
      outputFile: "unit.xml"
      suite: "unit"
