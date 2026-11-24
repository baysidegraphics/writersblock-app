"""Shared authenticated account controls, outside all twelve writing formats."""
from core.authentication import AuthenticationError


def sync_access_state(state, auth, license_valid, trial_valid):
    auth.access_check=lambda row: license_valid(row)[0] or trial_valid(row)[0]
    try:
        row=auth.refresh_account()
    except AuthenticationError:
        row=None
    licensed=bool(row and license_valid(row)[0])
    trial=bool(row and not licensed and trial_valid(row)[0])
    state['licensed_mode']=licensed
    state['demo_mode']=trial
    state['licensed_user_row']=row if licensed else None
    state['demo_user_row']=row if trial else None
    state['licensed_email']=auth.email if licensed else ''
    state['demo_email']=auth.email if trial else ''
    return licensed or trial


def bind_workspace(state,auth):
    """A new person must never inherit another person's unsaved workspace."""
    previous=state.get('_wbs_workspace_subject')
    # Legacy/unbound session state is not trusted after introducing Auth.
    if previous!=auth.subject:
        state.clear()
        state['_wbs_auth_controller']=auth
    state['_wbs_workspace_subject']=auth.subject


def render_auth_access(st,auth,context):
    panel=st.empty()
    with panel.container():
        _render_auth_panel(st,auth,context,panel)


def _matching_password(password,confirmation):
    if password != confirmation:
        raise AuthenticationError('The passwords do not match.')
    return password


_SECRET_WIDGETS=(
    'wbs_auth_password','wbs_auth_registration_password','wbs_auth_registration_confirm',
    'wbs_auth_confirmation_code','wbs_auth_recovery_code',
    'wbs_auth_new_password','wbs_auth_new_password_confirm','wbs_auth_email_code',
)


def _password_notice(st,message,error=False):
    # Clear secrets before widgets are constructed on the next run. This avoids
    # mutating instantiated widget state or keeping passwords after submission.
    st.session_state['_wbs_auth_clear_secret_widgets']=True
    st.session_state['_wbs_auth_password_notice']=(error,message)
    st.rerun()


def _render_auth_panel(st,auth,context,panel):
    if st.session_state.pop('_wbs_auth_clear_secret_widgets',False):
        for key in _SECRET_WIDGETS:
            st.session_state.pop(key,None)
    notice=st.session_state.pop('_wbs_auth_password_notice',None)
    if notice:
        (st.error if notice[0] else st.success)(notice[1])
    license_valid=context['is_license_access_valid']
    trial_valid=context['is_demo_access_valid']
    st.caption('Use your registered email and password. Confirm your email before signing in. Your existing projects, license and trial stay attached to your account.')
    method=st.radio('Account access',['Sign in','Register','Confirm email','Forgot password','Reset password'],key='wbs_auth_password_flow')
    try:
        if method=='Sign in':
            with st.form('wbs_password_signin',clear_on_submit=True):
                email=st.text_input('Account email',key='wbs_auth_password_email')
                password=st.text_input('Password',type='password',key='wbs_auth_password')
                submitted=st.form_submit_button('Sign in')
            if submitted:
                auth.sign_in_password(email,password)
                panel.empty()
                bind_workspace(st.session_state,auth)
                sync_access_state(st.session_state,auth,license_valid,trial_valid)
                st.session_state['_wbs_auth_clear_secret_widgets']=True
                st.rerun()
        elif method=='Register':
            with st.form('wbs_password_registration',clear_on_submit=True):
                email=st.text_input('Email',key='wbs_auth_registration_email')
                password=st.text_input('Create password (at least 12 characters)',type='password',key='wbs_auth_registration_password')
                confirmation=st.text_input('Confirm password',type='password',key='wbs_auth_registration_confirm')
                submitted=st.form_submit_button('Register')
            if submitted:
                auth.register_password(email,_matching_password(password,confirmation))
                _password_notice(st,'If registration is available, a confirmation email has been sent. Choose Confirm email and enter its code. Registration does not activate or change a license.')
        elif method=='Confirm email':
            with st.form('wbs_signup_confirmation',clear_on_submit=True):
                email=st.text_input('Registration email',key='wbs_auth_confirmation_email')
                code=st.text_input('Email confirmation code',type='password',key='wbs_auth_confirmation_code')
                confirm=st.form_submit_button('Confirm email')
                resend=st.form_submit_button('Resend confirmation')
            if confirm:
                auth.confirm_registration(email,code)
                _password_notice(st,'Email confirmed. Choose Sign in and enter your email and password.')
            elif resend:
                auth.resend_confirmation(email)
                _password_notice(st,'If eligible, a confirmation email has been sent.')
        elif method=='Forgot password':
            with st.form('wbs_password_recovery_request',clear_on_submit=True):
                email=st.text_input('Registered email',key='wbs_auth_recovery_request_email')
                submitted=st.form_submit_button('Send recovery email')
            if submitted:
                auth.request_password_recovery(email)
                _password_notice(st,'If eligible, a recovery email has been sent. Choose Reset password and enter its code.')
        elif method=='Reset password':
            if not auth.recovery_pending:
                with st.form('wbs_password_recovery_verify',clear_on_submit=True):
                    email=st.text_input('Recovery email',key='wbs_auth_recovery_email')
                    code=st.text_input('Recovery code',type='password',key='wbs_auth_recovery_code')
                    submitted=st.form_submit_button('Verify recovery code')
                if submitted:
                    auth.verify_recovery_code(email,code)
                    st.session_state['_wbs_auth_clear_secret_widgets']=True
                    st.rerun()
            else:
                with st.form('wbs_password_recovery_update',clear_on_submit=True):
                    password=st.text_input('New password (at least 12 characters)',type='password',key='wbs_auth_new_password')
                    confirmation=st.text_input('Confirm new password',type='password',key='wbs_auth_new_password_confirm')
                    submitted=st.form_submit_button('Update password')
                if submitted:
                    auth.complete_password_recovery(_matching_password(password,confirmation))
                    _password_notice(st,'Password updated. Choose Sign in and enter your new password.')
                if st.button('Cancel recovery',key='wbs_auth_cancel_recovery'):
                    auth.sign_out()
                    st.rerun()
        if auth.subject:
            st.caption('Your sign-in is verified. Signing in does not activate a license or reassign an existing account by email.')
            if st.button('Start / Resume 7-Day Trial',key='activate_demo_access',use_container_width=True):
                auth.start_trial(auth.email)
                panel.empty()
                sync_access_state(st.session_state,auth,license_valid,trial_valid)
                st.rerun()
            if st.button('Sign out',key='wbs_auth_pending_logout'):
                auth.sign_out()
                panel.empty()
                st.session_state.clear()
                st.rerun()
    except AuthenticationError as error:
        _password_notice(st,str(error),error=True)
