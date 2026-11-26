-- 03: activity logging, role checks, user creation, sign-in and sign-out
CREATE FUNCTION log_activity(
    p_user_id uuid, p_action_type text, p_description text,
    p_reference_type text DEFAULT NULL, p_reference_id uuid DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_id uuid;
BEGIN
    INSERT INTO activity_log (user_id, session_id, action_type, description, reference_type, reference_id)
    VALUES (
        p_user_id,
        (SELECT session_id FROM user_sessions
          WHERE user_id = p_user_id AND signed_out_at IS NULL
          ORDER BY signed_in_at DESC LIMIT 1),
        p_action_type, p_description, p_reference_type, p_reference_id
    )
    RETURNING activity_id INTO v_id;
    RETURN v_id;
END;
$$;

CREATE FUNCTION check_role(p_user_id uuid, p_allowed text[]) RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_role text;
    v_active boolean;
BEGIN
    SELECT user_role, is_active INTO v_role, v_active FROM app_users WHERE user_id = p_user_id;
    IF NOT FOUND OR NOT v_active THEN
        RAISE EXCEPTION 'Unknown or inactive user';
    END IF;
    IF NOT (v_role = ANY (p_allowed)) THEN
        RAISE EXCEPTION 'Your role (%) is not allowed to do this', v_role;
    END IF;
    RETURN v_role;
END;
$$;

CREATE FUNCTION create_user(
    p_full_name text, p_username text, p_pin text, p_role text,
    p_acting_user_id uuid DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_user_id uuid;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM app_users) THEN
        IF p_role <> 'owner' THEN
            RAISE EXCEPTION 'The first user must be the owner';
        END IF;
    ELSE
        PERFORM check_role(p_acting_user_id, ARRAY['owner']);
    END IF;

    IF p_pin !~ '^[0-9]{4,8}$' THEN
        RAISE EXCEPTION 'PIN must be 4 to 8 digits';
    END IF;

    INSERT INTO app_users (full_name, username, user_role, pin_hash)
    VALUES (p_full_name, lower(trim(p_username)), p_role, crypt(p_pin, gen_salt('bf')))
    RETURNING user_id INTO v_user_id;

    IF p_acting_user_id IS NOT NULL THEN
        PERFORM log_activity(p_acting_user_id, 'user_created',
                             'Created user ' || p_full_name || ' (' || p_role || ')', 'user', v_user_id);
    END IF;
    RETURN v_user_id;
END;
$$;

CREATE FUNCTION sign_in(p_username text, p_pin text) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    v_user app_users%ROWTYPE;
    v_session_id uuid;
BEGIN
    SELECT * INTO v_user FROM app_users WHERE username = lower(trim(p_username)) AND is_active;
    IF NOT FOUND OR v_user.pin_hash <> crypt(p_pin, v_user.pin_hash) THEN
        RAISE EXCEPTION 'Wrong username or PIN';
    END IF;

    UPDATE user_sessions
       SET signed_out_at = clock_timestamp(), sign_out_reason = 'new_sign_in'
     WHERE user_id = v_user.user_id AND signed_out_at IS NULL;

    INSERT INTO user_sessions (user_id) VALUES (v_user.user_id) RETURNING session_id INTO v_session_id;
    PERFORM log_activity(v_user.user_id, 'sign_in', v_user.full_name || ' signed in', 'session', v_session_id);
    RETURN v_session_id;
END;
$$;

CREATE FUNCTION sign_out(p_session_id uuid, p_reason text DEFAULT 'manual') RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_user_id uuid;
BEGIN
    SELECT user_id INTO v_user_id FROM user_sessions WHERE session_id = p_session_id AND signed_out_at IS NULL;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    PERFORM log_activity(v_user_id,
                         CASE WHEN p_reason = 'auto' THEN 'auto_sign_out' ELSE 'sign_out' END,
                         'Signed out (' || p_reason || ')', 'session', p_session_id);

    UPDATE user_sessions
       SET signed_out_at = clock_timestamp(), sign_out_reason = p_reason
     WHERE session_id = p_session_id;
END;
$$;
