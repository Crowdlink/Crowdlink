guard 'livereload', :apply_js_live => true, :appy_css_live => true do
  watch(%r{static/js/.+\.(js)$})
  watch(%r{static/css/.+\.(css)$})
  watch(%r{static/img/.+\.(png|gif|jpg)$})
  watch(%r{templates/.+\.(html)$})
end

guard 'coffeescript', :input => '', :output => 'static/js' do
  watch(%r{^.+\.coffee$})
end

#guard 'compass', :css_dir => 'static/css', :sass_dir => 'scss' do
#  watch(%r{^.+\.scss$})
#end

#guard 'less', :output => 'static/css' do
#    watch("less/bootstrap/bootstrap.less")
#end

guard :shell do
    watch(%r{^scss/.+\.scss$}) do
        `compass compile --force --css-dir="static/css" --sass-dir="scss" --images-dir="static/img" -s compressed`
        puts "Recompiled sass"
    end
end

guard :shell do
    watch(%r{^less/bootstrap/.+\.less$}) do
        `recess ./less/bootstrap/bootstrap.less --compile --compress > ./static/lib/css/bootstrap.min.css`
        puts "Recompiled bootstrap"
    end
end
