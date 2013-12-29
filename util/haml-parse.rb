#!/usr/bin/env ruby

require 'rubygems'
require 'rake'
require 'haml'
require 'json'

curr = File.expand_path(File.dirname(__FILE__))
configure = JSON.parse(File.read(curr + '/../application.json'))['public']

FileList.new(curr + '/../haml/**/*.haml').each do |filename|
  if filename =~ /([^\/]+)\.haml$/
    puts filename
    File.open(curr + '/../static/templates/' + $1 + '.html', 'w') do |f|
      f.write Haml::Engine.new(File.read(filename)).render(Object.new, configure)
    end
  end
end
