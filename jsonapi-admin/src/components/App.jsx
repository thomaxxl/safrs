/*
    The App component
    Here the routes and Header are created, based on the Config.json
*/
import './style/bootstrapstyle.css'
import '../style/style.css'
import {APP} from '../Config.jsx'
import React, { Component } from 'react'
import {  Route, Switch, HashRouter } from 'react-router-dom'
import { connect } from 'react-redux'
import { bindActionCreators } from 'redux'
import HeaderNavContainer from './HeaderNavContainer'
import Home from './Home'
import ApiObjectContainer from './ApiObjectContainer/ApiObjectContainer'
import * as ObjectAction from '../action/ObjectAction'
import * as ModalAction from '../action/ModalAction'
import * as InputAction from '../action/InputAction'
import * as SpinnerAction from '../action/SpinnerAction'
import {ItemInfo} from './Common/ItemInfo'

function genCollectionRoute(key) {
    /*
        Create a Route component for the collection specified by key
    */
    const mapStateToProps = state => ({
        objectKey: key,
        item: APP[key],
        api_data: state.object,
        inputflag: state.inputReducer
    })
    
    const mapDispatchToProps = dispatch => ({
        action: bindActionCreators(ObjectAction, dispatch),
        modalaction: bindActionCreators(ModalAction,dispatch),
        inputaction: bindActionCreators(InputAction,dispatch),
        spinnerAction: bindActionCreators(SpinnerAction,dispatch)
        //formaction: bindActionCreators(FormAction,dispatch),
        //getRelationship: getRelationship
    })
    
    const Results = connect(mapStateToProps, mapDispatchToProps)(ApiObjectContainer)
    const path = APP[key].path +'/'
    return <Route key={key + '_key'}  path={path} component={Results} name={key}/>
}

function genItemRoute(key) {
    /*
        Create a Route component for collection items:
        if there's a viewer defined for the items, the viewer will be rendered, otherwise the default ItemInfo viewer will be shown
    */
    const mapStateToProps = state => ({
        objectKey: key,
        api_data: state.object,
        item: APP[key]
    })

    const mapDispatchToProps = dispatch => ({
        action: bindActionCreators(ObjectAction, dispatch),
        modalaction: bindActionCreators(ModalAction,dispatch)
    })

    const component_info = APP[key]

    if(!component_info){
        alert('Invalid Component')
        return <div/>
    }
    const Viewer  = component_info.viewer ? component_info.viewer : ItemInfo
    const Results = connect(mapStateToProps, mapDispatchToProps)(Viewer)
    const item_path = `${component_info.path}/:itemId`
    const action_path = `${item_path}/:actionId`
    return <Route sensitive key={item_path} path={item_path} component={Results}>sdqdf</Route>
}

function genHome(){
    const mapStateToProps = state => ({        
        api_data: state.object,
        inputflag: state.inputReducer
    })
    
    const mapDispatchToProps = dispatch => ({
        action: bindActionCreators(ObjectAction, dispatch),
        modalaction: bindActionCreators(ModalAction,dispatch),
        inputaction: bindActionCreators(InputAction,dispatch),
        spinnerAction: bindActionCreators(SpinnerAction,dispatch)
        //formaction: bindActionCreators(FormAction,dispatch),
        //getRelationship: getRelationship
    })
    
    const Mapped_Home = connect(mapStateToProps, mapDispatchToProps)(Home)
    return <Route exact path="/" component={Mapped_Home}/>
}


class App extends Component {

    render() {
        /*
            collectionRoutes : routes specified by the APP "path" attributes (cfr. Config.json)
        */
        const collectionRoutes = Object.keys(APP).map((key) => [genItemRoute(key), genCollectionRoute(key)] )
        return <HashRouter>
                  <div>
                      <HeaderNavContainer/>
                      <Switch>
                          {genHome()}
                          {collectionRoutes}
                      </Switch>
                  </div>
                </HashRouter>  
    }
}

export default App