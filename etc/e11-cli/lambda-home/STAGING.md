# Staging Environment Setup

This document describes the staging environment setup for the lambda-home project.

## Overview

The staging environment provides a separate deployment target at `https://stage.csci-e-11.org/` that shares resources with production but allows for testing UI/UX changes and grading functionality.

## Architecture

### Shared Resources
- **DynamoDB Tables**: Both production and staging use the same users and sessions tables
- **Route53 Hosted Zone**: Same hosted zone for DNS management
- **ACM Certificate**: Wildcard certificate covering both `csci-e-11.org` and `*.csci-e-11.org`
- **OIDC Configuration**: Same HarvardKey OIDC setup

### Session Sharing
- Staging environment accepts cookies from the production domain (`csci-e-11.org`)
- Sessions created on production work on staging and vice versa
- This allows testing with existing authenticated sessions

### Domain Configuration
- **Production**: `https://csci-e-11.org/`
- **Staging**: `https://stage.csci-e-11.org/`

## Deployment

### Current Setup: Separate Stacks
The staging environment is deployed as a separate SAM stack from production. This allows independent deployments:

- **Production Stack**: `home-app` - bound to `csci-e-11.org`
- **Staging Stack**: `home-app-stage` - bound to `stage.csci-e-11.org`

**Benefits**: You can deploy to staging without affecting production, and vice versa.

```bash
# Deploy staging only (default)
make build
make deploy

# Deploy staging explicitly
make build-stage
make deploy-stage

# Deploy production only
make build-prod
make deploy-prod
```

### Deploy Commands

#### Current Separate Stack Approach
```bash
# Staging only (default)
make build
make deploy

# Or staging explicitly
make build-stage
make deploy-stage

# Production only
make build-prod
make deploy-prod

# Or use SAM directly
make generate-templates
sam build --parallel -t template-stage.yaml
sam deploy --stack-name home-app-stage --region us-east-1 -t template-stage.yaml
```

**Note**: Each environment is deployed independently, allowing you to test changes on staging without affecting production.

### Template Management

The templates are generated from parts using `cat`:

- **Production**: `template-top.yaml` + `template-common.yaml` + `template-bottom.yaml` → `template.yaml`
- **Staging**: `template-stage-top.yaml` + `template-common.yaml` + `template-stage-bottom.yaml` → `template-stage.yaml`

To regenerate templates after changes:
```bash
make generate-templates
```

### Environment Detection
The Lambda function automatically detects which environment it's running in by checking the `stage` field in the API Gateway event context:
- Production: `stage = "prod"` (or empty)
- Staging: `stage = "stage"`

## Testing

### What Works in Staging
- ✅ UI/UX testing
- ✅ Grading functionality
- ✅ Session management (using production sessions)
- ✅ API endpoints

### What Doesn't Work in Staging
- ❌ New user registration (OIDC redirects to production)
- ❌ New authentication flows (OIDC redirects to production)

### Testing Workflow
1. **Login on Production**: Visit `https://csci-e-11.org/` and authenticate
2. **Test on Staging**: Visit `https://stage.csci-e-11.org/` - your session will be available
3. **Test Changes**: Make UI/UX changes and test them on staging
4. **Deploy to Production**: When satisfied, deploy the same code to production

## Configuration

### Environment Variables
The staging environment uses the same environment variables as production:
- `COOKIE_DOMAIN`: Set to `csci-e-11.org` for both environments
- `DDB_TABLE_ARN`: Same DynamoDB table
- `SESSIONS_TABLE_NAME`: Same sessions table
- `OIDC_SECRET_ID`: Same OIDC configuration

### Cookie Domain Logic
The `get_cookie_domain(event)` function ensures that:
- Production sets cookies for `csci-e-11.org`
- Staging also sets cookies for `csci-e-11.org` (not `stage.csci-e-11.org`)
- This enables session sharing between environments

## Monitoring

### Logs
```bash
# Production logs
make tail

# Staging logs
make tail-stage
```

### URLs
```bash
# Show both URLs
make urls

# Show specific URLs
make prod-url
make stage-url
```

## Troubleshooting

### Common Issues

1. **Staging not accessible**: Check that the DNS record for `stage.csci-e-11.org` exists in Route53
2. **Sessions not working**: Verify that cookies are being set with domain `csci-e-11.org`
3. **OIDC redirects**: Remember that OIDC always redirects to production - this is expected behavior

### Debugging
- Check CloudWatch logs for both environments
- Verify ACM certificate covers both domains
- Ensure Route53 hosted zone contains both domain records

## Security Considerations

- Both environments share the same DynamoDB tables
- Sessions are shared between environments
- OIDC configuration is shared
- Consider this when testing sensitive operations

## Future Enhancements

Potential improvements for the staging environment:
- Separate DynamoDB tables for staging
- Staging-specific OIDC configuration
- Environment-specific feature flags
- Automated testing pipeline
