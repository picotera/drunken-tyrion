

jQuery(function($) {
    
    var RESULTS_SLEEP = 1000 * 5;
    
    var ENTER_KEY = 13;
    var ESC_KEY = 27;

    var idGen = function() {
        var i;
        var id = '';
        
        for (i=0; i<32; i++) {
            id += Math.floor(Math.random() * 16).toString(16);
        }
        
        return id;
    }
    
    var TodoApp = {
        init : function() {
            // Initializes the application
            this.$searchForm = $('#searchForm');
            this.$results = $('#results');
            this.$article = $('#article');
            
            this.finished = false;
            this.bindHandlers()
            // this.bindHandlers();
        },
        bindHandlers: function() {
            // Search handlers
            this.$searchForm.find('#submitForm').click(this.search.bind(this));
            
            // this.$results.on('click', '.article', this.getArticle.bind(this));
            /*
            // login handlers
            this.$loginForm.find('#login_btn').click(this.login.bind(this));
            this.$loginForm.find('#reg_btn').click(this.showForm.bind(this));
            
            // register handlers
            this.$regForm.find('#complete_reg').click(this.register.bind(this));
            this.$regForm.find('#back').click(this.showLogin.bind(this));
            
            // todo handlers
            this.$newTodo.keyup(this.createTodo.bind(this));
            $('#select').click(this.selectAll.bind(this));
            $('#clear').click(this.clear.bind(this));
            $('#remove').click(this.remove.bind(this));
            this.$logout.click(this.logout.bind(this));
            this.$todoList.on('change', '.complete', this.toggle.bind(this));
            this.$todoList.on('dblclick', '.edit', this.edit.bind(this));
            this.$todoList.on('keyup', '.editing', this.saveTodo.bind(this));
            this.$todoList.on('focusout', '.editing', this.saveTodo.bind(this));
            */
        },
        search: function(e) {
            var app = this;
            formData = app.$searchForm.serialize()
            
            app.showResults()
            
            $.ajax({
                url: '/search',
                method: 'POST',
                data: formData,
                success: function(data) {
                    data = jQuery.parseJSON(data);
                    id = data['id'];
                    console.log('Received search id: ' + id);
                    
                    app.getResults(id);
                },
                error: function(jqXHR) {
                    console.log('Error' + jqXHR)
                    app.showSearch();
                }
            });
        },
        getResults: function(id) {
            console.log('Getting ' +id);
            var app = this;
            $.ajax({
                url: '/results',
                method: 'GET',
                data: {
                    'id' : id,
                },
                success: function(data, status) {
                    console.log('Status: ' + status);
                    data = jQuery.parseJSON(data);
                    status = data['status'];
                    if (status == 'pending') {
                        console.log(RESULTS_SLEEP)
                        setTimeout(function () {
                            app.getResults(id);
                        }, RESULTS_SLEEP);
                        return;
                    }
                    console.log(data)
                    app.updateResults(data);
                },
                error: function(jqXHR) {
                    console.log('Error' + jqXHR)
                }
            });
        },
        updateResult: function(data, key) {
            data = data[key]
            if (data === undefined)
                return;
            
            console.log('Updating result: ' + data);
            this.$results.append('<header>' + key + '</header>');            
                
            status = data['status'];
            if (status == 'error') {
                console.log('Error: ' + data['reason']);
                this.$results.append('<div class="error">ERROR: ' + data['reason'] + '</div>');
                return;
            }
            
            results = data['results'];
            console.log(results.length);
            
            for (var i=0; i<results.length; i++) {
                console.log(results[i]);
                this.$results.append('<div class="result"><a class="article" href="/article?id=' + results[i]['id'] + '">' + results[i]['title'] + '</a> from ' + results[i]['source'] + ' score: ' + results[i]['score'] + '</div><br>');
            }
        },
        updateResults: function(data) {
            this.$results.html('');
            
            this.updateResult(data, 'google');
            this.updateResult(data, 'factiva');
            this.updateResult(data, 'lexis');
        },
        showSearch: function() {
            this.$results.hide();
            this.$searchForm.show();            
        },
        showResults: function() {
            this.$searchForm.hide();
            this.$results.show();   
        },
        register: function() {
            var app = this;
            var regPass = this.$regForm.find('#reg_pass').val();
            
            if (regPass != this.$regForm.find('#verify').val()) {
                this.$regMsg.css('color', 'red').html('Passwords do not match');
                return;
            }
            
            $.ajax({
                url: '/register',
                method: 'POST',
                data: {
                    username: this.$regForm.find('#reg_user').val(),
                    password: regPass,
                    fullname: this.$regForm.find('#fullname').val(),
                },
                success: function(data) {
                    app.$loginMsg.css('color', 'green').html('Registered successfuly');
                    app.showLogin();
                },
                error: function(jqXHR) {
                    if (jqXHR.status == 500) {
                        app.$regMsg.css('color', 'red').html(jqXHR.responseText);
                    } else {
                        app.$regMsg.html('Server returned error ' + status);
                    }                 
                }
            });          
            
        },
        login: function() {
            var app = this;
            
            $.ajax({
                url: '/login',
                method: 'GET',
                data: {
                    username: this.$username.val(),
                    password: this.$password.val(),
                },
                success: function(data) {
                    app.getTodos();
                },
                error: function(jqXHR) {
                    if (jqXHR.status == 500) {
                        app.$loginMsg.css('color', 'red').html(jqXHR.responseText);
                    } else {
                        app.$loginMsg.html('Server returned error ' + status);
                    }
                }
            });
        },
        logout: function(e) {
            this.showLogin();
            $.removeCookie('sessionId');
        },
    };

    TodoApp.init();
    
});