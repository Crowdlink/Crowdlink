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
