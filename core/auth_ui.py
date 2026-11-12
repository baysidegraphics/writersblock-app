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


def _render_auth_panel(st,auth,context,panel):
    license_valid=context['is_license_access_valid']
    trial_valid=context['is_demo_access_valid']
    st.caption('Sign in to your confirmed account. Your existing license, projects and versions stay attached to that account.')
    method=st.radio('Sign-in method',['Email code','Password'],key='wbs_auth_method')
    try:
        if method=='Password':
            with st.form('wbs_password_signin',clear_on_submit=True):
                email=st.text_input('Account email',key='wbs_auth_password_email')
                password=st.text_input('Password',type='password',key='wbs_auth_password')
                submitted=st.form_submit_button('Sign in')
            if submitted:
                auth.sign_in_password(email,password)
                panel.empty()
                bind_workspace(st.session_state,auth)
                sync_access_state(st.session_state,auth,license_valid,trial_valid)
                st.rerun()
        else:
            with st.form('wbs_email_signin',clear_on_submit=True):
                email=st.text_input('Account email',key='wbs_auth_code_email')
                send=st.form_submit_button('Send sign-in code')
            if send:
                auth.request_email_code(email)
                st.session_state['_wbs_auth_pending_email']=email.strip().lower()
                st.success('If available, a sign-in email has been sent. Enter the code from that email.')
            pending=st.session_state.get('_wbs_auth_pending_email')
            if pending:
                with st.form('wbs_verify_email_code',clear_on_submit=True):
                    code=st.text_input('Email sign-in code',type='password',key='wbs_auth_email_code')
                    verify=st.form_submit_button('Verify and sign in')
                if verify:
                    auth.verify_email_code(pending,code)
                    panel.empty()
                    bind_workspace(st.session_state,auth)
                    sync_access_state(st.session_state,auth,license_valid,trial_valid)
                    st.rerun()
        if auth.subject:
            st.caption('Signed in. Existing purchases require their approved account link; signing in does not activate or alter a license.')
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
        st.error(str(error))
