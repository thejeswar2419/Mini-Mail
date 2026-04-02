pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                git 'https://github.com/thejeswar2419/Mini-Mail.git'
            }
        }

        stage('Setup Python') {
            steps {
                bat 'python --version'
                bat 'pip --version'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat 'pip install -r requirements.txt'
            }
        }

        stage('Run App Check') {
            steps {
                bat 'echo Flask app syntax check...'
                bat 'python -m py_compile app.py'
            }
        }
    }

    post {
        success {
            echo 'CI Pipeline Successful'
        }
        failure {
            echo 'CI Pipeline Failed'
        }
    }
}