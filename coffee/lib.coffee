# These are development values, and will get overriden after deployment processing
STATIC_PATH = '/static/'
API_PATH = '/api/'
# These defns will be used all over the code, but because of their syntax will
# be subbed at deploymenet with configurable values
window.api_path = "#{API_PATH}"
window.static_path = "#{STATIC_PATH}"
