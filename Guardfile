guard 'livereload', :apply_js_live => true, :appy_css_live => true do
  watch(%r{static/js/.+\.(js)$})
  watch(%r{static/css/.+\.(css)$})
  watch(%r{static/img/.+\.(png|gif|jpg)$})
  watch(%r{templates/.+\.(html)$})
end

guard 'coffeescript', :input => '', :output => 'static/js' do
  watch(%r{^.+\.coffee$})
end

guard 'compass' do
  watch(%r{^.+\.sass$})
end

#guard 'less', :output => 'static/css' do
#    watch("less/bootstrap/bootstrap.less")
#end

guard :shell do
    watch(%r{^less/bootstrap/.+\.less$}) do
        `recess ./less/bootstrap/bootstrap.less --compress > ./static/css/bootstrap.css`
        puts "Recompiled bootstrap"
    end
end
