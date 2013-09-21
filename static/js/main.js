(function() {
  window.bind_import = function(id) {
    var options;
    options = {
      success: function(data) {
        if (data[0] === "success") {
          $("#alert").removeClass();
          $("#alert").addClass("g");
          return $("#alert").html(data[1]);
        } else {
          $("#alert").removeClass();
          $("#alert").addClass("b");
          return $("#alert").html(data[1]);
        }
      },
      type: 'POST',
      dataType: 'json'
    };
    return $("#" + id).ajaxForm(options);
  };

}).call(this);
