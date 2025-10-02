# Contributing to Soccer Scanner

Thank you for your interest in contributing to Soccer Scanner! This document provides guidelines for contributing to the project.

## 🚀 Quick Start for Contributors

### Local Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/SOCCER-SCANNER.git
   cd SOCCER-SCANNER
   ```

2. **Set Up Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Add your API key to .env file
   ```

4. **Run Locally**
   ```bash
   python app.py
   # Visit http://localhost:5000
   ```

## 📝 Making Changes

### Before You Start

1. Check existing issues and pull requests
2. Create an issue to discuss major changes
3. Fork the repository and create a new branch

### Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code style
   - Keep changes focused and atomic
   - Test your changes locally

3. **Test your changes**
   ```bash
   # Test the application
   python app.py
   
   # Test imports
   python -c "import app; print('OK')"
   
   # Test with gunicorn
   gunicorn --bind 0.0.0.0:8000 app:app --check-config
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   # Then create a Pull Request on GitHub
   ```

## 🎨 Code Style Guidelines

### Python
- Follow PEP 8 style guide
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

### HTML/CSS
- Use semantic HTML5 elements
- Maintain consistent indentation (2 spaces)
- Keep CSS organized by component
- Use mobile-first responsive design

### JavaScript
- Use modern ES6+ syntax
- Add comments for complex logic
- Follow existing code patterns

## 🧪 Testing

Before submitting a PR:

1. **Test locally**
   ```bash
   python app.py
   # Manually test all features
   ```

2. **Check imports**
   ```bash
   python -c "import app"
   ```

3. **Validate deployment config**
   ```bash
   gunicorn app:app --check-config
   ```

## 📦 Deployment Testing

If your changes affect deployment:

1. Test with different deployment platforms
2. Verify environment variables work correctly
3. Check health endpoint: `/health`
4. Review GitHub Actions workflow results

## 🐛 Bug Reports

When reporting bugs, include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Detailed steps to recreate
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: OS, Python version, browser
6. **Screenshots**: If applicable

## 💡 Feature Requests

For feature requests, include:

1. **Problem**: What problem does this solve?
2. **Solution**: Proposed solution or feature
3. **Alternatives**: Other solutions considered
4. **Use Cases**: Real-world usage examples

## 📋 Pull Request Process

1. **Update Documentation**: If adding features, update README.md
2. **Test Thoroughly**: Ensure all features work
3. **Keep it Small**: Focus on one feature/fix per PR
4. **Clear Description**: Explain what and why
5. **Link Issues**: Reference related issues

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] Changes tested locally
- [ ] Documentation updated if needed
- [ ] No breaking changes (or clearly documented)
- [ ] Deployment configuration still valid
- [ ] Health check endpoint works

## 🔒 Security

If you discover a security vulnerability:

1. **Do NOT** open a public issue
2. Email the maintainers privately
3. Provide detailed information about the vulnerability
4. Wait for confirmation before public disclosure

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Recognition

Contributors will be recognized in:
- GitHub contributors list
- Release notes for significant contributions
- Project documentation

## 💬 Questions?

- Open an issue for questions
- Check existing documentation
- Review closed issues for similar questions

## 🌟 Types of Contributions We Welcome

- 🐛 Bug fixes
- ✨ New features
- 📝 Documentation improvements
- 🎨 UI/UX enhancements
- 🔧 Configuration improvements
- 🧪 Test coverage
- 🚀 Performance improvements
- ♿ Accessibility enhancements

Thank you for contributing to Soccer Scanner! ⚽
